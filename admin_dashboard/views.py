import datetime
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.utils import timezone

from accounts.models import CustomUser
from upi.models import BankAccount, Transaction
from loans.models import LoanApplication
from .models import Notification


# ── Preset notification templates ──────────────────────────────────────────
PRESET_TEMPLATES = {
    'welcome': {
        'title': 'Welcome to SpendSmart Bank! 🎉',
        'body': 'Your account has been created. We\'re glad to have you on board. '
                'Once your account is approved, you can start transacting.',
        'icon': 'bi-house-heart',
    },
    'approved': {
        'title': 'Account Approved ✅',
        'body': 'Great news! Your account has been approved and your initial deposit has been credited. '
                'You can now send money, apply for loans, and use all features.',
        'icon': 'bi-check-circle',
    },
    'freeze_warning': {
        'title': 'Account Freeze Notice ⚠️',
        'body': 'Your account has been temporarily frozen due to suspicious activity. '
                'Please contact our support team to resolve this.',
        'icon': 'bi-shield-exclamation',
    },
    'loan_approved': {
        'title': 'Loan Application Approved 💰',
        'body': 'Congratulations! Your loan application has been approved. '
                'The amount will be disbursed to your account shortly.',
        'icon': 'bi-cash-coin',
    },
    'loan_rejected': {
        'title': 'Loan Application Update',
        'body': 'We regret to inform you that your loan application could not be approved at this time. '
                'You may apply again after 90 days or contact support for details.',
        'icon': 'bi-file-x',
    },
    'festival_offer': {
        'title': '🎊 Special Festival Offer!',
        'body': 'Celebrate the festive season with SpendSmart Bank! '
                'Get zero processing fees on personal loans up to ₹5 lakhs this month. '
                'Limited time offer — apply now!',
        'icon': 'bi-gift',
    },
    'rate_update': {
        'title': 'Interest Rate Update 📊',
        'body': 'We have revised our savings account interest rates effective from this month. '
                'Your account now earns a higher rate. Check your account for details.',
        'icon': 'bi-graph-up-arrow',
    },
    'referral': {
        'title': 'Refer & Earn 🤝',
        'body': 'Love SpendSmart Bank? Refer a friend and earn ₹200 cashback when they open an account '
                'and make their first transaction. Share your referral code from your profile page.',
        'icon': 'bi-people',
    },
    'custom': {
        'title': '',
        'body': '',
        'icon': 'bi-bell',
    },
}


def admin_required(view_func):
    def check(user):
        return user.is_active and (user.is_staff or user.is_admin)
    return user_passes_test(check, login_url='accounts:login')(view_func)


@admin_required
def dashboard_view(request):
    users = CustomUser.objects.all().order_by('-date_joined')
    accounts = BankAccount.objects.select_related('user').all()
    loans = LoanApplication.objects.select_related('user').all()

    transactions_qs = Transaction.objects.select_related(
        'sender_account__user', 'receiver_account__user'
    ).order_by('-timestamp')
    paginator = Paginator(transactions_qs, 50)
    transactions = paginator.get_page(request.GET.get('page'))

    today = timezone.now().date()
    flagged_count  = transactions_qs.filter(is_flagged=True, resolved=False).count()
    success_count  = transactions_qs.filter(status='SUCCESS').count()
    failed_count   = transactions_qs.filter(status='FAILED').count()
    today_volume   = transactions_qs.filter(
        status='SUCCESS', timestamp__date=today
    ).aggregate(s=Sum('amount'))['s'] or 0
    total_balance  = accounts.aggregate(s=Sum('balance'))['s'] or 0
    audit_logs     = transactions_qs[:40]
    unresolved_failed = transactions_qs.filter(status='FAILED', resolved=False)[:25]

    # Pending: is_approved=False AND is_active=True (not yet rejected)
    pending_accounts     = accounts.filter(is_approved=False, is_active=True, is_rejected=False)
    # Rejected: is_rejected=True
    rejected_accounts    = accounts.filter(is_rejected=True)
    # All Accounts tab should exclude rejected accounts entirely
    all_accounts         = accounts.exclude(is_rejected=True)
    # Needs-review counts for rail-nav badge dots
    pending_loans        = loans.filter(status='PENDING')
    pending_transactions = transactions_qs.filter(status='PENDING')

    # Notifications for the messaging tab
    notifications = Notification.objects.select_related('recipient').order_by('-created_at')[:50]
    customers = CustomUser.objects.filter(is_staff=False, is_admin=False).order_by('username')

    return render(request, "admin_dashboard/dashboard.html", {
        "users":               users,
        "accounts":            accounts,
        "all_accounts":        all_accounts,
        "transactions":        transactions,
        "loans":               loans,
        "flagged_count":       flagged_count,
        "success_count":       success_count,
        "failed_count":        failed_count,
        "today_volume":        today_volume,
        "total_balance":       total_balance,
        "audit_logs":          audit_logs,
        "unresolved_failed":   unresolved_failed,
        "pending_accounts":    pending_accounts,
        "rejected_accounts":   rejected_accounts,
        "pending_loans":       pending_loans,
        "pending_transactions": pending_transactions,
        "notifications":       notifications,
        "customers":           customers,
        "preset_templates":    PRESET_TEMPLATES,
    })


@admin_required
def customer_detail_view(request, customer_id):
    """Full customer detail: KYC, accounts, transactions, loans, notifications."""
    customer = get_object_or_404(CustomUser, customer_id=customer_id)
    accs = customer.accounts.all()
    txns = Transaction.objects.filter(
        Q(sender_account__user=customer) | Q(receiver_account__user=customer)
    ).select_related('sender_account__user', 'receiver_account__user').order_by('-timestamp')[:50]
    loans = customer.loan_applications.all().order_by('-applied_at')
    notifs = customer.notifications.order_by('-created_at')[:20]

    # ── Quick-glance stats for the header strip ──────────────────────────
    total_balance = sum((a.balance for a in accs if a.is_approved), Decimal('0.00'))
    all_txns_for_stats = Transaction.objects.filter(
        Q(sender_account__user=customer) | Q(receiver_account__user=customer)
    )
    success_count = all_txns_for_stats.filter(status='SUCCESS').count()
    failed_count = all_txns_for_stats.filter(status='FAILED').count()
    total_txn_count = all_txns_for_stats.count()
    active_loan_count = loans.filter(status__in=['PENDING', 'APPROVED', 'DISBURSED']).count()

    return render(request, "admin_dashboard/customer_detail.html", {
        "customer":      customer,
        "accs":          accs,
        "txns":          txns,
        "loans":         loans,
        "notifs":        notifs,
        "total_balance":     total_balance,
        "total_txn_count":   total_txn_count,
        "success_count":     success_count,
        "failed_count":      failed_count,
        "active_loan_count": active_loan_count,
    })


@admin_required
def send_notification_view(request):
    """Send a preset or custom notification to one customer or broadcast to all."""
    if request.method != 'POST':
        return redirect('admin_dashboard:dashboard')

    preset    = request.POST.get('preset', 'custom')
    recipient_id = request.POST.get('recipient_id', '').strip()   # blank = broadcast
    custom_title = request.POST.get('custom_title', '').strip()
    custom_body  = request.POST.get('custom_body', '').strip()

    tmpl = PRESET_TEMPLATES.get(preset, PRESET_TEMPLATES['custom'])
    title = custom_title or tmpl['title']
    body  = custom_body  or tmpl['body']
    icon  = tmpl['icon']

    if not title or not body:
        messages.error(request, "Notification title and body are required.")
        return redirect('admin_dashboard:dashboard')

    from django.http import JsonResponse as JR
    if recipient_id:
        recipient = get_object_or_404(CustomUser, id=recipient_id)
        Notification.objects.create(
            recipient=recipient, preset=preset,
            title=title, body=body, icon=icon,
        )
        msg = f'Notification sent to {recipient.username}.'
        messages.success(request, msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JR({'status': 'ok', 'message': msg})
    else:
        customers = CustomUser.objects.filter(is_staff=False, is_admin=False)
        Notification.objects.bulk_create([
            Notification(recipient=c, preset=preset, title=title, body=body, icon=icon)
            for c in customers
        ])
        msg = f'Broadcast sent to {customers.count()} customers.'
        messages.success(request, msg)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JR({'status': 'ok', 'message': msg})

    return redirect('admin_dashboard:dashboard')


@admin_required
def resolve_transaction_view(request, txn_id):
    txn = get_object_or_404(Transaction, id=txn_id)
    if request.method == 'POST':
        note = request.POST.get('resolution_note', '').strip()
        txn.is_flagged = False
        txn.resolved = True
        txn.resolution_note = note or "Resolved by admin."
        txn.save(update_fields=['is_flagged', 'resolved', 'resolution_note'])
        messages.success(request, f"Transaction {txn.reference_id} marked as resolved.")
    return redirect('admin_dashboard:dashboard')


@admin_required
def freeze_account_view(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id)
    if request.method == 'POST':
        account.is_active = False
        account.save(update_fields=['is_active'])
        messages.success(request, f"Account {account.account_number} frozen.")
    return redirect('admin_dashboard:dashboard')


@admin_required
def approve_account_view(request, account_id):
    from django.http import JsonResponse as JR
    account = get_object_or_404(BankAccount, id=account_id)
    if request.method == 'POST':
        account.is_approved = True
        account.balance     = account.requested_balance
        account.is_active   = True
        account.save(update_fields=['is_approved', 'balance', 'is_active'])

        # Auto-send welcome notification
        Notification.objects.create(
            recipient=account.user,
            preset='welcome',
            title='Welcome to SpendSmart Bank 🎉',
            body=(
                f'Congratulations {account.user.first_name or account.user.username}! '
                f'Your account ({account.account_number}) has been approved and '
                f'₹{account.balance} has been credited. '
                'You can now send money, apply for loans, and use all features. '
                'Thank you for banking with SpendSmart!'
            ),
            icon='bi-check-circle-fill',
        )

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if is_ajax:
            return JR({'status': 'ok',
                       'message': f'Account {account.account_number} approved — ₹{account.balance} credited.',
                       'account_id': account_id})
        messages.success(request, f"Account {account.account_number} approved — ₹{account.balance} credited.")
    return HttpResponseRedirect(reverse('admin_dashboard:dashboard') + '?tab=pending#tabPendingLink')


@admin_required
def reject_account_view(request, account_id):
    from django.http import JsonResponse as JR
    account = get_object_or_404(BankAccount, id=account_id)
    if request.method == 'POST':
        # Mark account rejected (inactive + not approved + not eligible to unfreeze)
        account.is_active   = False
        account.is_approved = False
        account.is_rejected = True
        # is_rejected must be included here or it's never persisted to the DB,
        # which is what let a rejected account fall back to "pending" on unfreeze.
        account.save(update_fields=['is_active', 'is_approved', 'is_rejected'])

        Notification.objects.create(
            recipient=account.user,
            preset='custom',
            title='Account Application Update',
            body=(
                f'We were unable to verify your account application (A/C: {account.account_number}). '
                'Your KYC documents could not be confirmed at this time. '
                'Please visit a branch or contact support with valid ID proof to re-apply.'
            ),
            icon='bi-exclamation-triangle',
        )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JR({'status': 'warning',
                       'message': f'Account {account.account_number} rejected — please show popup modal.',
                       'account_id': account_id})
        messages.warning(request, f"Account {account.account_number} rejected — popup shown.")
    return HttpResponseRedirect(reverse('admin_dashboard:dashboard') + '?tab=pending#tabPendingLink')


@admin_required
def unfreeze_account_view(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id)
    if account.is_rejected:                  # ← guard: rejected accounts can't be unfrozen
        messages.error(request, "This account was rejected, not frozen. It cannot be unfrozen.")
        return redirect('admin_dashboard:dashboard')
    if request.method == 'POST':
        account.is_active = True
        account.save(update_fields=['is_active'])
        messages.success(request, f"Account {account.account_number} unfrozen.")
    return redirect('admin_dashboard:dashboard')


@admin_required
def xbrl_statement_view(request, customer_id):
    """
    Export a customer's transaction statement as XBRL/XML.
    Follows a simplified XBRL-like structure for banking statements.
    """
    customer = get_object_or_404(CustomUser, customer_id=customer_id)
    accs = customer.accounts.all()
    txns = Transaction.objects.filter(
        Q(sender_account__user=customer) | Q(receiver_account__user=customer)
    ).order_by('-timestamp')[:200]

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    total_sent     = sum(t.amount for t in txns if t.sender_account and t.sender_account.user == customer and t.status == 'SUCCESS')
    total_received = sum(t.amount for t in txns if t.receiver_account and t.receiver_account.user == customer and t.status == 'SUCCESS')

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<xbrl xmlns="http://www.xbrl.org/2003/instance"',
        '      xmlns:spsb="http://spendsmartbank.in/xbrl/2024"',
        f'     contextRef="period_{now.strftime("%Y%m%d")}"',
        f'     generatedAt="{now.isoformat()}">',
        '',
        '  <!-- ── Entity Information ───────────────────────── -->',
        '  <spsb:Entity>',
        f'    <spsb:BankName>SpendSmart Bank</spsb:BankName>',
        f'    <spsb:StatementDate>{now.strftime("%Y-%m-%d")}</spsb:StatementDate>',
        f'    <spsb:CustomerID>{customer.customer_id}</spsb:CustomerID>',
        f'    <spsb:CustomerName>{customer.get_full_name() or customer.username}</spsb:CustomerName>',
        f'    <spsb:Email>{customer.email}</spsb:Email>',
        f'    <spsb:PAN>{customer.pan_number}</spsb:PAN>',
        '  </spsb:Entity>',
        '',
        '  <!-- ── Linked Accounts ───────────────────────────── -->',
        '  <spsb:Accounts>',
    ]
    for acc in accs:
        lines += [
            '    <spsb:Account>',
            f'      <spsb:AccountNumber>{acc.account_number}</spsb:AccountNumber>',
            f'      <spsb:AccountType>{acc.account_type}</spsb:AccountType>',
            f'      <spsb:UPIID>{acc.upi_id}</spsb:UPIID>',
            f'      <spsb:Balance decimals="2">{acc.balance}</spsb:Balance>',
            f'      <spsb:IsApproved>{str(acc.is_approved).lower()}</spsb:IsApproved>',
            f'      <spsb:IsActive>{str(acc.is_active).lower()}</spsb:IsActive>',
            '    </spsb:Account>',
        ]
    lines += [
        '  </spsb:Accounts>',
        '',
        '  <!-- ── Summary ──────────────────────────────────── -->',
        '  <spsb:Summary>',
        f'    <spsb:TotalTransactions>{txns.count()}</spsb:TotalTransactions>',
        f'    <spsb:TotalSent decimals="2">{total_sent}</spsb:TotalSent>',
        f'    <spsb:TotalReceived decimals="2">{total_received}</spsb:TotalReceived>',
        '  </spsb:Summary>',
        '',
        '  <!-- ── Transactions ─────────────────────────────── -->',
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
            f'      <spsb:FailureReason>{t.failure_reason or ""}</spsb:FailureReason>',
            '    </spsb:Transaction>',
        ]
    lines += [
        '  </spsb:Transactions>',
        '</xbrl>',
    ]

    xml_content = '\n'.join(lines)
    filename = f"statement_{customer.customer_id}_{now.strftime('%Y%m%d')}.xml"
    response = HttpResponse(xml_content, content_type='application/xml')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response