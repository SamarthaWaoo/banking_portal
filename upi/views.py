from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect

from .models import BankAccount, Transaction


@login_required
def dashboard_view(request):
    accounts = request.user.accounts.filter(is_active=True)
    recent_txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    )[:5]
    total_balance = sum([acc.balance for acc in accounts]) if accounts else Decimal('0.00')
    return render(request, 'upi/dashboard.html', {
        'accounts': accounts,
        'recent_txns': recent_txns,
        'total_balance': total_balance,
    })


@login_required
def send_money_view(request):
    my_accounts = request.user.accounts.filter(is_active=True)

    if not request.user.pin_hash:
        messages.warning(request, "Please set your transaction PIN before sending money.")
        return redirect('accounts:set_pin')

    if request.method == 'POST':
        sender_account_id = request.POST.get('sender_account')
        receiver_upi_id = request.POST.get('receiver_upi_id', '').strip()
        amount_raw = request.POST.get('amount', '0')
        note = request.POST.get('note', '')[:140]
        pin = request.POST.get('pin', '')

        try:
            amount = Decimal(amount_raw)
        except Exception:
            messages.error(request, "Enter a valid amount.")
            return redirect('upi:send_money')

        sender_account = my_accounts.filter(id=sender_account_id).first()

        # ---- Validation chain (each failure recorded, none silently ignored) ----
        error = None
        if not sender_account:
            error = "Invalid sender account."
        elif amount <= 0:
            error = "Amount must be greater than zero."
        elif not request.user.check_transaction_pin(pin):
            error = "Incorrect transaction PIN."
        elif sender_account.balance < amount:
            error = "Insufficient balance."
        elif sender_account.amount_transferred_today() + amount > sender_account.daily_transfer_limit:
            error = "This transfer exceeds your daily transfer limit."

        receiver_account = None
        if not error:
            receiver_account = BankAccount.objects.filter(upi_id=receiver_upi_id, is_active=True).first()
            if not receiver_account:
                error = "Receiver UPI ID not found."
            elif receiver_account.id == sender_account.id:
                error = "You cannot send money to the same account."

        if error:
            # Log a FAILED transaction for audit-trail completeness
            Transaction.objects.create(
                sender_account=sender_account, receiver_account=receiver_account,
                amount=amount if amount > 0 else Decimal('0.01'),
                transaction_type='SEND', status='FAILED', note=note, failure_reason=error,
            )
            messages.error(request, error)
            return redirect('upi:send_money')

        # ---- Atomic money movement: all-or-nothing ----
        try:
            with db_transaction.atomic():
                # select_for_update prevents race conditions on concurrent transfers
                sender_locked = BankAccount.objects.select_for_update().get(id=sender_account.id)
                receiver_locked = BankAccount.objects.select_for_update().get(id=receiver_account.id)

                if sender_locked.balance < amount:
                    raise ValueError("Insufficient balance.")

                sender_locked.balance -= amount
                receiver_locked.balance += amount
                sender_locked.save()
                receiver_locked.save()

                Transaction.objects.create(
                    sender_account=sender_locked, receiver_account=receiver_locked,
                    amount=amount, transaction_type='SEND', status='SUCCESS', note=note,
                    sender_balance_after=sender_locked.balance,
                    receiver_balance_after=receiver_locked.balance,
                )
            messages.success(request, f"₹{amount} sent successfully to {receiver_upi_id}.")
            return redirect('upi:dashboard')
        except Exception as e:
            messages.error(request, f"Transaction failed: {e}")
            return redirect('upi:send_money')

    return render(request, 'upi/send_money.html', {'accounts': my_accounts})


@login_required
def transaction_history_view(request):
    txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    )

    status_filter = request.GET.get('status')
    if status_filter:
        txns = txns.filter(status=status_filter)

    return render(request, 'upi/transactions.html', {'txns': txns})


@login_required
def download_statement_pdf(request):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    )[:50]

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="statement_{request.user.customer_id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>SpendSmart Bank</b>", styles['Title']))
    elements.append(Paragraph(f"Account Statement — {request.user.get_full_name() or request.user.username}", styles['Heading3']))
    elements.append(Paragraph(f"Customer ID: {request.user.customer_id}", styles['Normal']))
    elements.append(Spacer(1, 12))

    data = [["Date", "Reference ID", "Type", "Amount (₹)", "Status", "Note"]]
    for t in txns:
        data.append([
            t.timestamp.strftime('%d-%m-%Y %H:%M'),
            t.reference_id,
            t.transaction_type,
            f"{t.amount}",
            t.status,
            t.note[:30],
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0a2540')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f5f9')]),
    ]))
    elements.append(table)

    doc.build(elements)
    return response
