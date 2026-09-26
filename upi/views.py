import json
from datetime import date as datetime_date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction as db_transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    BankAccount, Transaction, RecentContact, Beneficiary,
    Budget, SPEND_CATEGORIES, CATEGORY_META,
)
from accounts.models import CustomUser


# ─────────────────────────────────────────────
# AJAX: Search users by username / UPI ID
# Returns actual UPI IDs so the form works.
# ─────────────────────────────────────────────
def search_users(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse([], safe=False)

    # Search by username or UPI ID across BankAccount
    accounts = BankAccount.objects.filter(is_active=True, is_approved=True).filter(
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
    accounts = BankAccount.objects.filter(is_active=True, is_approved=True).select_related('user')

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


def _month_range(year, month):
    """Returns (start, end) datetime bounds for a calendar month, timezone-aware.
    Used instead of timestamp__year=/timestamp__month= lookups, which require
    MySQL's CONVERT_TZ() and silently match nothing if timezone tables aren't
    loaded on the DB server."""
    start = timezone.make_aware(
        __import__('datetime').datetime(year, month, 1, 0, 0, 0)
    )
    if month == 12:
        end = timezone.make_aware(__import__('datetime').datetime(year + 1, 1, 1, 0, 0, 0))
    else:
        end = timezone.make_aware(__import__('datetime').datetime(year, month + 1, 1, 0, 0, 0))
    return start, end


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────
@login_required
def dashboard_view(request):
    from admin_dashboard.models import Notification

    # Staff/admin accounts don't have banking data of their own to show —
    # give them a personal admin-info view instead of the customer dashboard.
    if request.user.is_staff or request.user.is_admin:
        return render(request, 'upi/dashboard.html', {
            'is_admin_view': True,
        })

    accounts = request.user.accounts.all()
    recent_txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    ).select_related('sender_account__user', 'receiver_account__user')[:5]
    approved_accounts = accounts.filter(is_approved=True, is_active=True)
    pending_accounts  = accounts.filter(is_approved=False)
    total_balance = sum(acc.balance for acc in approved_accounts) if approved_accounts else Decimal('0.00')

    newly_approved = None
    if request.session.pop('account_just_approved', False):
        newly_approved = approved_accounts.first()

    # Notifications for this user — count unread BEFORE slicing
    notifs_qs    = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    unread_count = notifs_qs.filter(is_read=False).count()
    notifs_qs.filter(is_read=False).update(is_read=True)
    notifications = notifs_qs[:10]

    has_transactions = recent_txns.exists()

    # ── Spending insights: 6-month cash-flow trend ──────────────────────
    month_labels, sent_series, received_series = [], [], []
    today = timezone.localtime(timezone.now()).date()
    for i in range(5, -1, -1):
        month_index = today.month - i
        year = today.year
        while month_index <= 0:
            month_index += 12
            year -= 1
        month_labels.append(datetime_date(year, month_index, 1).strftime('%b'))

        m_start, m_end = _month_range(year, month_index)
        sent = Transaction.objects.filter(
            sender_account__user=request.user, status='SUCCESS',
            timestamp__gte=m_start, timestamp__lt=m_end,
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        received = Transaction.objects.filter(
            receiver_account__user=request.user, status='SUCCESS',
            timestamp__gte=m_start, timestamp__lt=m_end,
        ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        sent_series.append(float(sent))
        received_series.append(float(received))

    # ── Spending insights: this-month category breakdown ────────────────
    this_month_start, this_month_end = _month_range(today.year, today.month)
    this_month_spend = Transaction.objects.filter(
        sender_account__user=request.user, status='SUCCESS',
        timestamp__gte=this_month_start, timestamp__lt=this_month_end,
    ).values('category').annotate(total=Sum('amount')).order_by('-total')

    category_labels, category_values, category_colors = [], [], []
    for row in this_month_spend:
        meta = CATEGORY_META.get(row['category'], CATEGORY_META['OTHER'])
        category_labels.append(dict(SPEND_CATEGORIES).get(row['category'], row['category']))
        category_values.append(float(row['total']))
        category_colors.append(meta['color'])

    total_this_month_spend = sum(category_values) if category_values else 0
    current_month_spend = sent_series[-1] if sent_series else 0
    current_month_received = received_series[-1] if received_series else 0

    # ── Budgets snapshot (top 3 by usage) ────────────────────────────────
    budgets = list(request.user.budgets.all())
    budgets.sort(key=lambda b: b.percent_used(), reverse=True)
    budget_snapshot = budgets[:3]

    return render(request, 'upi/dashboard.html', {
        'accounts':         accounts,
        'recent_txns':      recent_txns,
        'total_balance':    total_balance,
        'pending_accounts': pending_accounts,
        'newly_approved':   newly_approved,
        'notifications':    notifications,
        'unread_count':     unread_count,
        'has_transactions': has_transactions,
        'chart_labels':     json.dumps(month_labels),
        'chart_sent':       json.dumps(sent_series),
        'chart_received':   json.dumps(received_series),
        'category_labels':  json.dumps(category_labels),
        'category_values':  json.dumps(category_values),
        'category_colors':  json.dumps(category_colors),
        'has_spend_data':   bool(category_values),
        'total_this_month_spend': total_this_month_spend,
        'current_month_spend': current_month_spend,
        'current_month_received': current_month_received,
        'budget_snapshot':  budget_snapshot,
        'has_budgets':      bool(budgets),
    })


# ─────────────────────────────────────────────
# Fetch notifications as JSON (for live-update without reload)
# ─────────────────────────────────────────────
@login_required
def fetch_notifications(request):
    from admin_dashboard.models import Notification
    from django.http import JsonResponse
    all_qs = Notification.objects.filter(recipient=request.user)
    unread = all_qs.filter(is_read=False).count()
    notifs_qs = all_qs.order_by('-created_at')[:15]
    # Mark all as read NOW (after counting)
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    data = [
        {
            'id':         n.id,
            'title':      n.title,
            'body':       n.body,
            'icon':       n.icon,
            'is_read':    n.is_read,
            'created_at': n.created_at.strftime('%d %b %Y, %H:%M'),
        }
        for n in notifs_qs
    ]
    return JsonResponse({'notifications': data, 'unread_count': unread})


@login_required
def notifications_unread_count(request):
    """Lightweight, read-only unread count for the topbar bell badge.
    Does NOT mark anything read — that only happens when the bell is opened
    and fetch_notifications is called."""
    from admin_dashboard.models import Notification
    from django.http import JsonResponse
    unread = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread_count': unread})


# ─────────────────────────────────────────────
# Budgets — set monthly spending goals per category
# ─────────────────────────────────────────────
@login_required
def budgets_view(request):
    if request.method == 'POST':
        category = request.POST.get('category', '')
        limit_raw = request.POST.get('monthly_limit', '0')
        if category not in dict(SPEND_CATEGORIES):
            messages.error(request, "Choose a valid category.")
            return redirect('upi:budgets')
        try:
            limit = Decimal(limit_raw)
            if limit <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a valid monthly limit greater than ₹0.")
            return redirect('upi:budgets')

        Budget.objects.update_or_create(
            user=request.user, category=category,
            defaults={'monthly_limit': limit}
        )
        messages.success(
            request,
            f"Budget for {dict(SPEND_CATEGORIES).get(category)} set to ₹{limit:,.2f}/month."
        )
        return redirect('upi:budgets')

    existing = {b.category: b for b in request.user.budgets.all()}
    rows = []
    for code, label in SPEND_CATEGORIES:
        if code == 'TRANSFER':
            continue  # transfers aren't a "spending" goal category
        budget = existing.get(code)
        rows.append({
            'code': code,
            'label': label,
            'meta': CATEGORY_META.get(code, CATEGORY_META['OTHER']),
            'budget': budget,
        })

    total_limit = sum((b.monthly_limit for b in existing.values()), Decimal('0.00'))
    total_spent = sum((b.spent_this_month() for b in existing.values()), Decimal('0.00'))

    return render(request, 'upi/budgets.html', {
        'rows': rows,
        'total_limit': total_limit,
        'total_spent': total_spent,
        'total_remaining': total_limit - total_spent,
        'has_budgets': bool(existing),
    })


@login_required
def delete_budget(request, budget_id):
    budget = Budget.objects.filter(id=budget_id, user=request.user).first()
    if budget:
        budget.delete()
        messages.success(request, "Budget removed.")
    return redirect('upi:budgets')


# ─────────────────────────────────────────────
# Send Money
# ─────────────────────────────────────────────
@login_required
def send_money_view(request):
    my_accounts = request.user.accounts.filter(is_active=True, is_approved=True)

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
        category = request.POST.get('category', 'OTHER')
        if category not in dict(SPEND_CATEGORIES):
            category = 'OTHER'
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
        elif not sender_account.is_approved:
            error = "Your account is pending admin approval. You cannot send money yet."
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
                upi_id=receiver_upi, is_active=True, is_approved=True
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
                category=category,
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
                    category=category,
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
                category=category,
                failure_reason=f"System error: {e}",
            )
            messages.error(request, f"Transaction failed: {e}. No money was deducted.")
            return redirect('upi:send_money')

    return render(request, 'upi/send_money.html', {
        'accounts': my_accounts,
        'recent_contacts': recent_contacts,
        'prefill_receiver': prefill_receiver,
        'beneficiaries': beneficiaries,
        'category_choices': SPEND_CATEGORIES,
        'category_meta': CATEGORY_META,
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
# Download Statement — machine-readable XBRL/XML
# (kept for back-office / accounting-system ingestion)
# ─────────────────────────────────────────────
@login_required
def download_statement_xml(request):
    import datetime
    txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    ).order_by('-timestamp')[:200]
    accs = request.user.accounts.all()

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    total_sent     = sum(t.amount for t in txns if t.sender_account and t.sender_account.user == request.user and t.status == 'SUCCESS')
    total_received = sum(t.amount for t in txns if t.receiver_account and t.receiver_account.user == request.user and t.status == 'SUCCESS')

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<xbrl xmlns="http://www.xbrl.org/2003/instance"',
        '      xmlns:spsb="http://spendsmartbank.in/xbrl/2024"',
        f'     generatedAt="{now.isoformat()}">',
        '',
        '  <spsb:Entity>',
        f'    <spsb:BankName>SpendSmart Bank</spsb:BankName>',
        f'    <spsb:StatementDate>{now.strftime("%Y-%m-%d")}</spsb:StatementDate>',
        f'    <spsb:CustomerID>{request.user.customer_id}</spsb:CustomerID>',
        f'    <spsb:CustomerName>{request.user.get_full_name() or request.user.username}</spsb:CustomerName>',
        '  </spsb:Entity>',
        '',
        '  <spsb:Accounts>',
    ]
    for acc in accs:
        lines += [
            '    <spsb:Account>',
            f'      <spsb:AccountNumber>{acc.account_number}</spsb:AccountNumber>',
            f'      <spsb:AccountType>{acc.account_type}</spsb:AccountType>',
            f'      <spsb:UPIID>{acc.upi_id}</spsb:UPIID>',
            f'      <spsb:Balance decimals="2">{acc.balance}</spsb:Balance>',
            '    </spsb:Account>',
        ]
    lines += [
        '  </spsb:Accounts>',
        '',
        f'  <spsb:TotalSent decimals="2">{total_sent}</spsb:TotalSent>',
        f'  <spsb:TotalReceived decimals="2">{total_received}</spsb:TotalReceived>',
        '',
        '  <spsb:Transactions>',
    ]
    for t in txns:
        sender   = t.sender_account.user.username   if t.sender_account   else ''
        receiver = t.receiver_account.user.username if t.receiver_account else ''
        lines += [
            '    <spsb:Transaction>',
            f'      <spsb:ReferenceID>{t.reference_id}</spsb:ReferenceID>',
            f'      <spsb:Timestamp>{t.timestamp.isoformat()}</spsb:Timestamp>',
            f'      <spsb:Type>{t.transaction_type}</spsb:Type>',
            f'      <spsb:Amount decimals="2">{t.amount}</spsb:Amount>',
            f'      <spsb:Status>{t.status}</spsb:Status>',
            f'      <spsb:Sender>{sender}</spsb:Sender>',
            f'      <spsb:Receiver>{receiver}</spsb:Receiver>',
            f'      <spsb:Note>{t.note or ""}</spsb:Note>',
            '    </spsb:Transaction>',
        ]
    lines += ['  </spsb:Transactions>', '</xbrl>']

    xml_content = '\n'.join(lines)
    fname = f"statement_{request.user.customer_id}_{now.strftime('%Y%m%d')}.xml"
    response = HttpResponse(xml_content, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ─────────────────────────────────────────────
# Download Statement — PDF (what the UI actually offers customers)
# ─────────────────────────────────────────────
@login_required
def download_statement(request):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT
    import io

    now = timezone.now()
    txns = Transaction.objects.filter(
        Q(sender_account__user=request.user) | Q(receiver_account__user=request.user)
    ).select_related('sender_account__user', 'receiver_account__user').order_by('-timestamp')[:100]
    accs = request.user.accounts.all()

    total_sent = sum(
        (t.amount for t in txns if t.sender_account and t.sender_account.user == request.user and t.status == 'SUCCESS'),
        Decimal('0.00')
    )
    total_received = sum(
        (t.amount for t in txns if t.receiver_account and t.receiver_account.user == request.user and t.status == 'SUCCESS'),
        Decimal('0.00')
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=16 * mm, leftMargin=16 * mm, rightMargin=16 * mm,
        title="SpendSmart Bank Statement",
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor('#111827')
    accent = colors.HexColor('#7C3AED')
    muted = colors.HexColor('#6B7280')

    h1 = ParagraphStyle('h1', parent=styles['Heading1'], textColor=navy, fontSize=18, spaceAfter=2)
    small_muted = ParagraphStyle('small_muted', parent=styles['Normal'], textColor=muted, fontSize=9)
    right_muted = ParagraphStyle('right_muted', parent=small_muted, alignment=TA_RIGHT)

    story = []
    story.append(Paragraph("SpendSmart Bank", h1))
    story.append(Paragraph("Account Statement · Simulated digital banking platform", small_muted))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", color=accent, thickness=1.4))
    story.append(Spacer(1, 10))

    info_data = [
        ["Customer", request.user.get_full_name() or request.user.username],
        ["Customer ID", request.user.customer_id],
        ["Statement generated", now.strftime('%d %b %Y, %H:%M UTC')],
    ]
    info_table = Table(info_data, colWidths=[45 * mm, 100 * mm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), muted),
        ('TEXTCOLOR', (1, 0), (1, -1), navy),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Linked Accounts", styles['Heading3']))
    acc_rows = [["Account Number", "Type", "UPI ID", "Balance"]]
    for acc in accs:
        acc_rows.append([acc.masked_number(), acc.get_account_type_display(), acc.upi_id, f"Rs. {acc.balance:,.2f}"])
    acc_table = Table(acc_rows, colWidths=[45 * mm, 32 * mm, 55 * mm, 32 * mm])
    acc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#E5E7EB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(acc_table)
    story.append(Spacer(1, 14))

    summary_data = [[
        Paragraph(f"<b>Total Sent</b><br/><font size=13 color='#DC2626'>Rs. {total_sent:,.2f}</font>", styles['Normal']),
        Paragraph(f"<b>Total Received</b><br/><font size=13 color='#16A34A'>Rs. {total_received:,.2f}</font>", styles['Normal']),
        Paragraph(f"<b>Net</b><br/><font size=13 color='#111827'>Rs. {(total_received - total_sent):,.2f}</font>", styles['Normal']),
    ]]
    summary_table = Table(summary_data, colWidths=[54 * mm, 54 * mm, 54 * mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F9FAFB')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph(f"Transactions (last {len(txns)})", styles['Heading3']))
    txn_rows = [["Date", "Reference", "Type", "Category", "Amount", "Status"]]
    for t in txns:
        is_debit = bool(t.sender_account and t.sender_account.user == request.user)
        sign = '-' if is_debit else '+'
        txn_rows.append([
            t.timestamp.strftime('%d %b %Y'),
            t.reference_id,
            'Sent' if is_debit else 'Received',
            t.get_category_display(),
            f"{sign} Rs. {t.amount:,.2f}",
            t.status,
        ])
    txn_table = Table(txn_rows, colWidths=[24 * mm, 32 * mm, 20 * mm, 30 * mm, 30 * mm, 22 * mm], repeatRows=1)
    txn_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#E5E7EB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(txn_table)
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", color=colors.HexColor('#E5E7EB'), thickness=0.6))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This is a system-generated statement from a simulated digital banking platform. "
        "No real money or KYC is involved.",
        small_muted
    ))

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()

    fname = f"statement_{request.user.customer_id}_{now.strftime('%Y%m%d')}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    return response


# ─────────────────────────────────────────────
# Download a single-transaction Receipt (PDF)
# ─────────────────────────────────────────────
@login_required
def transaction_receipt(request, txn_id):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    import io

    txn = get_object_or_404(Transaction, id=txn_id)
    is_party = (
        (txn.sender_account and txn.sender_account.user == request.user) or
        (txn.receiver_account and txn.receiver_account.user == request.user)
    )
    if not is_party:
        raise Http404("Receipt not found.")

    is_debit = bool(txn.sender_account and txn.sender_account.user == request.user)
    status_colors = {
        'SUCCESS': colors.HexColor('#16A34A'),
        'FAILED': colors.HexColor('#DC2626'),
        'PENDING': colors.HexColor('#D97706'),
        'FLAGGED': colors.HexColor('#D97706'),
    }

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A5,
        topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
        title=f"Receipt {txn.reference_id}",
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor('#111827')
    accent = colors.HexColor('#7C3AED')
    muted = colors.HexColor('#6B7280')

    center = ParagraphStyle('center', parent=styles['Normal'], alignment=TA_CENTER)
    brand = ParagraphStyle('brand', parent=styles['Heading2'], alignment=TA_CENTER, textColor=navy)
    amount_style = ParagraphStyle('amount', parent=styles['Heading1'], alignment=TA_CENTER, textColor=navy, fontSize=26)
    status_style = ParagraphStyle(
        'status', parent=styles['Normal'], alignment=TA_CENTER,
        textColor=status_colors.get(txn.status, muted), fontSize=11
    )

    story = [
        Paragraph("SpendSmart Bank", brand),
        Paragraph("Payment Receipt", ParagraphStyle('sub', parent=center, textColor=muted, fontSize=9)),
        Spacer(1, 10),
        HRFlowable(width="100%", color=accent, thickness=1.2),
        Spacer(1, 14),
        Paragraph(("- " if is_debit else "+ ") + f"Rs. {txn.amount:,.2f}", amount_style),
        Spacer(1, 4),
        Paragraph(txn.status, status_style),
        Spacer(1, 16),
    ]

    rows = [
        ["Reference ID", txn.reference_id],
        ["Date & Time", txn.timestamp.strftime('%d %b %Y, %H:%M')],
        ["Type", "Debit (Sent)" if is_debit else "Credit (Received)"],
        ["Category", txn.get_category_display()],
        ["From", txn.sender_account.upi_id if txn.sender_account else "—"],
        ["To", txn.receiver_account.upi_id if txn.receiver_account else "—"],
        ["Note", txn.note or "—"],
    ]
    table = Table(rows, colWidths=[40 * mm, 78 * mm])
    table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('TEXTCOLOR', (0, 0), (0, -1), muted),
        ('TEXTCOLOR', (1, 0), (1, -1), navy),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, colors.HexColor('#F3F4F6')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(table)
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", color=colors.HexColor('#E5E7EB'), thickness=0.6))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Simulated transaction — no real money moved. Generated by SpendSmart Bank.",
        ParagraphStyle('foot', parent=center, textColor=muted, fontSize=7.5)
    ))

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()

    fname = f"receipt_{txn.reference_id}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
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



# ─────────────────────────────────────────────
# Add Amount (deposit into approved account)
# ─────────────────────────────────────────────
@login_required
def add_amount_view(request):
    if request.method == 'POST':
        account_id = request.POST.get('account_id')
        amount_raw = request.POST.get('amount', '0').strip()
        pin = request.POST.get('pin', '')

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a valid amount.")
            return redirect('upi:dashboard')

        account = BankAccount.objects.filter(
            id=account_id, user=request.user, is_active=True, is_approved=True
        ).first()
        if not account:
            messages.error(request, "Invalid or unapproved account.")
            return redirect('upi:dashboard')
        if amount < Decimal('1'):
            messages.error(request, "Minimum deposit is ₹1.")
            return redirect('upi:dashboard')

        if not request.user.pin_hash:
            messages.warning(request, "Please set your transaction PIN before adding money.")
            return redirect('accounts:set_pin')

        # ── Lockout check ──────────────────────────────────────────────
        if request.user.is_pin_locked():
            secs = request.user.pin_lock_remaining_seconds()
            messages.error(
                request,
                f"Too many incorrect PINs. Your transfers are locked for "
                f"{secs // 60}m {secs % 60}s. Try again later."
            )
            return redirect('upi:dashboard')

        # ── PIN check ─────────────────────────────────────────────────
        if not request.user.check_transaction_pin(pin):
            request.user.register_failed_pin()   # increments + locks if threshold hit
            remaining = request.user.MAX_PIN_ATTEMPTS - request.user.failed_pin_attempts
            if request.user.is_pin_locked():
                messages.error(
                    request,
                    f"Incorrect PIN. Account locked for {request.user.PIN_LOCKOUT_MINUTES} minutes "
                    f"after {request.user.MAX_PIN_ATTEMPTS} failed attempts."
                )
            else:
                messages.error(request, f"Incorrect transaction PIN. {remaining} attempt(s) remaining.")
            return redirect('upi:dashboard')

        # ── Correct PIN → credit the account ─────────────────────────────
        with db_transaction.atomic():
            locked_account = BankAccount.objects.select_for_update().get(id=account.id)
            locked_account.balance += amount
            locked_account.save(update_fields=['balance'])

        # Successful PIN use → reset the failure counter
        request.user.reset_pin_attempts()

        messages.success(request, f"₹{amount:,.2f} added to your account successfully!")
    return redirect('upi:dashboard')