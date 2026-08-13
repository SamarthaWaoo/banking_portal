from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import BankAccount, Transaction, RecentContact, Beneficiary
from accounts.models import CustomUser


# ─────────────────────────────────────────────
# AJAX: Search users by username / UPI ID
# Returns actual UPI IDs so the form works.
# ─────────────────────────────────────────────
def search_users(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 1:
        return JsonResponse([], safe=False)

    # Search by username or UPI ID across BankAccount
    accounts = BankAccount.objects.filter(is_active=True).filter(
        Q(user__username__icontains=query) |
        Q(upi_id__icontains=query) |
        Q(user__first_name__icontains=query) |
        Q(user__last_name__icontains=query)
    ).select_related('user').distinct()

    if request.user.is_authenticated:
        accounts = accounts.exclude(user=request.user)

    accounts = accounts[:8]

    results = [
        {
            'username': acc.user.get_full_name() or acc.user.username,
            'upi_id': acc.upi_id,
            'account_type': acc.get_account_type_display(),
        }
        for acc in accounts
    ]
    return JsonResponse(results, safe=False)


# ─────────────────────────────────────────────
# AJAX: Return ALL active users, for the "Send To" dropdown
# shown before the user starts typing.
# ─────────────────────────────────────────────
def get_all_users(request):
    accounts = BankAccount.objects.filter(is_active=True).select_related('user')

    if request.user.is_authenticated:
        accounts = accounts.exclude(user=request.user)

    results = [
        {
            'username': acc.user.get_full_name() or acc.user.username,
            'upi_id': acc.upi_id,
            'account_type': acc.get_account_type_display(),
        }
        for acc in accounts.order_by('user__username')[:200]
    ]
    return JsonResponse(results, safe=False)


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────
@login_required
def dashboard_view(request):
    accounts = request.user.accounts.filter(is_active=True)
    recent_txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    ).select_related('sender_account__user', 'receiver_account__user')[:5]
    total_balance = sum(acc.balance for acc in accounts) if accounts else Decimal('0.00')
    return render(request, 'upi/dashboard.html', {
        'accounts': accounts,
        'recent_txns': recent_txns,
        'total_balance': total_balance,
    })


# ─────────────────────────────────────────────
# Send Money
# ─────────────────────────────────────────────
@login_required
def send_money_view(request):
    my_accounts = request.user.accounts.filter(is_active=True)

    if not request.user.pin_hash:
        messages.warning(request, "Please set your transaction PIN before sending money.")
        return redirect('accounts:set_pin')

    # Recent contacts for the "quick send" panel
    recent_contacts = RecentContact.objects.filter(
        user=request.user
    ).select_related('contact_account__user')[:6]

    # Saved beneficiaries
    beneficiaries = Beneficiary.objects.filter(
        user=request.user
    ).select_related('account__user')

    # Pre-fill receiver from ?receiver= query param (from "Send Again" link)
    prefill_receiver = request.GET.get('receiver', '')

    if request.method == 'POST':
        sender_account_id = request.POST.get('sender_account')
        receiver_upi = request.POST.get('receiver_upi', '').strip()
        amount_raw = request.POST.get('amount', '0')
        note = request.POST.get('note', '')[:140]
        pin = request.POST.get('pin', '')

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a valid amount.")
            return redirect('upi:send_money')

        sender_account = my_accounts.filter(id=sender_account_id).first()

        # ── Lockout check ──────────────────────────────────────────────
        if request.user.is_pin_locked():
            secs = request.user.pin_lock_remaining_seconds()
            messages.error(
                request,
                f"Too many incorrect PINs. Your transfers are locked for "
                f"{secs // 60}m {secs % 60}s. Try again later."
            )
            return redirect('upi:send_money')

        # ── Validation chain (every failure is recorded for audit) ──────
        error = None
        if not sender_account:
            error = "Invalid sender account."
        elif not sender_account.is_active:
            error = "This account is frozen. Contact support."
        elif amount <= 0:
            error = "Amount must be greater than zero."
        elif not request.user.check_transaction_pin(pin):
            request.user.register_failed_pin()   # increments + locks if threshold hit
            remaining = request.user.MAX_PIN_ATTEMPTS - request.user.failed_pin_attempts
            if request.user.is_pin_locked():
                error = (
                    f"Incorrect PIN. Account locked for {request.user.PIN_LOCKOUT_MINUTES} minutes "
                    f"after {request.user.MAX_PIN_ATTEMPTS} failed attempts."
                )
            else:
                error = f"Incorrect transaction PIN. {remaining} attempt(s) remaining."
        elif sender_account.balance < amount:
            error = "Insufficient balance."
        elif sender_account.amount_transferred_today() + amount > sender_account.daily_transfer_limit:
            remaining_limit = sender_account.daily_transfer_limit - sender_account.amount_transferred_today()
            error = (
                f"Daily transfer limit exceeded. "
                f"You can still send up to ₹{remaining_limit:.2f} today."
            )

        receiver_account = None
        if not error:
            receiver_account = BankAccount.objects.filter(
                upi_id=receiver_upi, is_active=True
            ).select_related('user').first()
            if not receiver_account:
                error = "Receiver UPI ID not found. Please check and try again."
            elif receiver_account.id == sender_account.id:
                error = "You cannot send money to the same account."

        # ── Log every failure for the admin audit trail ─────────────────
        if error:
            Transaction.objects.create(
                sender_account=sender_account,
                receiver_account=receiver_account,
                amount=amount if amount > 0 else Decimal('0.01'),
                transaction_type='SEND',
                status='FAILED',
                note=note,
                failure_reason=error,
                is_flagged=('PIN' in error),   # flag PIN-related failures
            )
            messages.error(request, error)
            return redirect('upi:send_money')

        # ── Atomic money movement ────────────────────────────────────────
        try:
            with db_transaction.atomic():
                sender_locked = BankAccount.objects.select_for_update().get(id=sender_account.id)
                receiver_locked = BankAccount.objects.select_for_update().get(id=receiver_account.id)

                # Double-check balance inside the lock (race-condition safety)
                if sender_locked.balance < amount:
                    raise ValueError("Insufficient balance (checked at transfer time).")

                sender_locked.balance -= amount
                receiver_locked.balance += amount
                sender_locked.save()
                receiver_locked.save()

                Transaction.objects.create(
                    sender_account=sender_locked,
                    receiver_account=receiver_locked,
                    amount=amount,
                    transaction_type='SEND',
                    status='SUCCESS',
                    note=note,
                    sender_balance_after=sender_locked.balance,
                    receiver_balance_after=receiver_locked.balance,
                )

                # Update/create recent contact
                RecentContact.objects.update_or_create(
                    user=request.user,
                    contact_account=receiver_locked,
                    defaults={'last_used': timezone.now()}
                )

            # Successful PIN use → reset the failure counter
            request.user.reset_pin_attempts()

            receiver_name = receiver_account.user.get_full_name() or receiver_account.user.username
            messages.success(
                request,
                f"₹{amount} sent successfully to {receiver_name} ({receiver_upi})."
            )
            return redirect('upi:dashboard')

        except Exception as e:
            # Atomic block rolled back — no money moved
            Transaction.objects.create(
                sender_account=sender_account,
                receiver_account=receiver_account,
                amount=amount,
                transaction_type='SEND',
                status='FAILED',
                note=note,
                failure_reason=f"System error: {e}",
            )
            messages.error(request, f"Transaction failed: {e}. No money was deducted.")
            return redirect('upi:send_money')

    return render(request, 'upi/send_money.html', {
        'accounts': my_accounts,
        'recent_contacts': recent_contacts,
        'prefill_receiver': prefill_receiver,
        'beneficiaries': beneficiaries,
    })


# ─────────────────────────────────────────────
# Transaction History
# ─────────────────────────────────────────────
@login_required
def transaction_history_view(request):
    txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    ).select_related('sender_account__user', 'receiver_account__user')

    status_filter = request.GET.get('status')
    if status_filter:
        txns = txns.filter(status=status_filter)

    return render(request, 'upi/transactions.html', {'txns': txns})


# ─────────────────────────────────────────────
# Download PDF Statement
# ─────────────────────────────────────────────
@login_required
def download_statement_pdf(request):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    )[:50]

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="statement_{request.user.customer_id}.pdf"'
    )

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>SpendSmart Bank</b>", styles['Title']))
    elements.append(Paragraph(
        f"Account Statement — {request.user.get_full_name() or request.user.username}",
        styles['Heading3']
    ))
    elements.append(Paragraph(f"Customer ID: {request.user.customer_id}", styles['Normal']))
    elements.append(Spacer(1, 12))

    data = [["Date", "Reference ID", "Type", "Amount (₹)", "Status", "Note"]]
    for t in txns:
        data.append([
            t.timestamp.strftime('%d-%m-%Y %H:%M'),
            t.reference_id,
            t.transaction_type,
            str(t.amount),
            t.status,
            t.note[:30] if t.note else "—",
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


# ─────────────────────────────────────────────
# Add Beneficiary (Save a recipient as favourite)
# ─────────────────────────────────────────────
@login_required
def add_beneficiary(request):
    if request.method == 'POST':
        upi_id = request.POST.get('upi_id', '').strip()
        nickname = request.POST.get('nickname', '').strip()
        account = BankAccount.objects.filter(upi_id=upi_id, is_active=True).first()
        if not account:
            messages.error(request, f"UPI ID '{upi_id}' not found.")
        elif account.user == request.user:
            messages.error(request, "You cannot add yourself as a beneficiary.")
        else:
            _, created = Beneficiary.objects.get_or_create(
                user=request.user, account=account,
                defaults={'nickname': nickname or (account.user.get_full_name() or account.user.username)}
            )
            if created:
                messages.success(request, f"Beneficiary '{nickname or account.user.username}' saved.")
            else:
                messages.info(request, "This account is already in your beneficiaries.")
    return redirect('upi:send_money')


# ─────────────────────────────────────────────
# Remove Beneficiary
# ─────────────────────────────────────────────
@login_required
def remove_beneficiary(request, beneficiary_id):
    ben = Beneficiary.objects.filter(id=beneficiary_id, user=request.user).first()
    if ben:
        ben.delete()
        messages.success(request, "Beneficiary removed.")
    return redirect('upi:send_money')

