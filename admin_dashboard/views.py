from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q
from django.utils import timezone

from accounts.models import CustomUser
from upi.models import BankAccount, Transaction
from loans.models import LoanApplication


def admin_required(view_func):
    """
    Allow access only to users who are staff (is_staff=True) OR
    have the is_admin flag set.  Staff flag is the Django standard
    and is what the Django admin uses, so we honour both.
    """
    def check(user):
        return user.is_active and (user.is_staff or user.is_admin)
    return user_passes_test(check, login_url='accounts:login')(view_func)


@admin_required
def dashboard_view(request):
    users = CustomUser.objects.all().order_by('-date_joined')
    accounts = BankAccount.objects.select_related('user').all()
    loans = LoanApplication.objects.select_related('user').all()

    # ── Transactions (paginated) ────────────────────────────────────────
    transactions_qs = Transaction.objects.select_related(
        'sender_account__user', 'receiver_account__user'
    ).order_by('-timestamp')
    paginator = Paginator(transactions_qs, 50)
    transactions = paginator.get_page(request.GET.get('page'))

    # ── Summary stats ───────────────────────────────────────────────────
    today = timezone.now().date()
    flagged_count   = transactions_qs.filter(is_flagged=True, resolved=False).count()
    success_count   = transactions_qs.filter(status='SUCCESS').count()
    failed_count    = transactions_qs.filter(status='FAILED').count()
    today_volume    = transactions_qs.filter(
        status='SUCCESS', timestamp__date=today
    ).aggregate(s=Sum('amount'))['s'] or 0
    total_balance   = accounts.aggregate(s=Sum('balance'))['s'] or 0

    # ── Audit log: 40 most recent operation events ──────────────────────
    # We use Transactions themselves as the audit log:
    # every operation (success or failure) produces a Transaction row.
    audit_logs = transactions_qs[:40]

    # ── Failed transactions that haven't been resolved yet ──────────────
    unresolved_failed = transactions_qs.filter(status='FAILED', resolved=False)[:25]
    resolved_failed   = transactions_qs.filter(status='FAILED', resolved=True).order_by('-timestamp')[:10]

    return render(request, "admin_dashboard/dashboard.html", {
        "users":             users,
        "accounts":          accounts,
        "transactions":      transactions,
        "loans":             loans,
        "flagged_count":     flagged_count,
        "success_count":     success_count,
        "failed_count":      failed_count,
        "today_volume":      today_volume,
        "total_balance":     total_balance,
        "audit_logs":        audit_logs,
        "unresolved_failed": unresolved_failed,
        "resolved_failed":   resolved_failed,
    })


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
        messages.success(
            request,
            f"Account {account.account_number} ({account.user.username}) has been frozen."
        )
    return redirect('admin_dashboard:dashboard')


@admin_required
def unfreeze_account_view(request, account_id):
    account = get_object_or_404(BankAccount, id=account_id)
    if request.method == 'POST':
        account.is_active = True
        account.save(update_fields=['is_active'])
        messages.success(
            request,
            f"Account {account.account_number} ({account.user.username}) has been unfrozen."
        )
    return redirect('admin_dashboard:dashboard')
