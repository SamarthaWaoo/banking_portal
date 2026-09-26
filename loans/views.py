from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import LoanApplicationForm
from .models import LoanApplication


# -----------------------------
# Apply for Loan
# -----------------------------
@login_required
def apply_view(request):
    if request.method == 'POST':
        post_data = request.POST.copy()

        # Convert tenure years → months if months field is empty
        tenure_raw = post_data.get('tenure_months', '').strip()
        if not tenure_raw:
            years_raw = post_data.get('tenure_years', '').strip()
            if years_raw.isdigit() and int(years_raw) > 0:
                post_data['tenure_months'] = str(int(years_raw) * 12)

        # Validate credit_score manually (field is outside the ModelForm)
        cs_raw = post_data.get('credit_score', '').strip()
        cs_error = None
        cs_value = None
        try:
            cs_value = int(cs_raw)
            if not (300 <= cs_value <= 900):
                cs_error = 'Credit score must be between 300 and 900.'
        except (ValueError, TypeError):
            cs_error = 'Enter a valid credit score (300–900).'

        form = LoanApplicationForm(post_data)
        if form.is_valid() and not cs_error:
            application = form.save(commit=False)
            application.user = request.user
            application.credit_score = cs_value
            application.status = 'PENDING'
            application.decision_reason = ''
            application.save()
            messages.success(
                request,
                f"Application {application.application_id} sent — please wait for admin approval."
            )
            return redirect('loans:my_loans')
        # pass cs_error to template if needed
    else:
        form = LoanApplicationForm()
        cs_error = None
    return render(request, 'loans/apply.html', {'form': form, 'cs_error': cs_error})


# -----------------------------
# My Loans
# -----------------------------
@login_required
def my_loans_view(request):
    loans = request.user.loan_applications.all()
    account = request.user.accounts.first()
    account_approved = bool(account and account.is_approved)
    return render(request, 'loans/my_loans.html', {
        'loans': loans,
        'account_approved': account_approved,
    })


# Statuses for which a repayment schedule has actually started ticking
REPAYMENT_STARTED_STATUSES = ['DISBURSED', 'CLOSED', 'DEFAULTED']
# Statuses for which we show the (possibly not-yet-started) amortization table
SCHEDULE_VISIBLE_STATUSES = ['APPROVED', 'DISBURSED', 'CLOSED', 'DEFAULTED']


def _build_repayment_context(loan):
    """
    Shared helper: builds the amortization schedule (annotated per-row with
    paid/unpaid) plus the repayment-progress summary numbers, used by both
    the customer-facing and admin-facing loan detail views.
    """
    schedule = loan.amortization_schedule() if loan.status in SCHEDULE_VISIBLE_STATUSES else []
    total_interest = sum(row['interest'] for row in schedule) if schedule else 0
    total_payable  = round(float(loan.loan_amount) + total_interest, 2)

    repayment_started = loan.status in REPAYMENT_STARTED_STATUSES
    months_paid   = loan.repayments_made
    months_left   = max(loan.tenure_months - months_paid, 0) if repayment_started else loan.tenure_months

    # The next month that's actually outstanding, and the REAL calendar date
    # it's due — not "due the instant the previous one was paid". Only once
    # today's date reaches that due date does it actually count as due now.
    next_due_month = (months_paid + 1) if (repayment_started and months_left > 0) else None
    next_due_date  = loan.get_next_due_date()
    today = timezone.now().date()
    days_until_due = (next_due_date - today).days if next_due_date else None
    due_now = bool(next_due_date and today >= next_due_date)

    unpaid_months = []
    for row in schedule:
        if repayment_started:
            row['paid'] = row['month'] <= months_paid
            if not row['paid']:
                unpaid_months.append(row['month'])
        else:
            # Loan hasn't been disbursed yet — nothing is "due" so there's
            # no meaningful paid/unpaid state. Template shows "—" for this.
            row['paid'] = None

    return {
        'schedule':          schedule,
        'total_interest':    round(total_interest, 2),
        'total_payable':     total_payable,
        'repayment_started': repayment_started,
        'months_paid':       months_paid,
        'months_left':       months_left,
        'next_due_month':    next_due_month,
        'next_due_date':     next_due_date,
        'days_until_due':    days_until_due,
        'due_now':           due_now,
        'unpaid_months':     unpaid_months,
        'remaining_amount':  loan.outstanding_balance,
    }


# -----------------------------
# Loan Detail (customer + staff can view their own / any application)
# -----------------------------
@login_required
def loan_detail_view(request, application_id):
    is_staff_viewer = request.user.is_staff or getattr(request.user, 'is_admin', False)
    if is_staff_viewer:
        loan = get_object_or_404(LoanApplication, application_id=application_id)
    else:
        loan = get_object_or_404(LoanApplication, application_id=application_id, user=request.user)

    tenure_years = round(loan.tenure_months / 12, 1)
    disposable   = round(float(loan.monthly_salary) - float(loan.monthly_expenses), 2)

    context = {
        'loan': loan,
        'tenure_years': tenure_years,
        'disposable_income': disposable,
    }
    context.update(_build_repayment_context(loan))
    return render(request, 'loans/loan_detail.html', context)


# ─────────────────────────────────────────────
# Admin Loan Detail (full info for approve/reject page)
# ─────────────────────────────────────────────
@user_passes_test(lambda u: u.is_staff or getattr(u, "is_admin", False))
def admin_loan_detail_view(request, application_id):
    loan = get_object_or_404(LoanApplication, application_id=application_id)
    context = {
        'loan':              loan,
        'rejection_reasons': LOAN_REJECTION_REASONS,
    }
    context.update(_build_repayment_context(loan))
    return render(request, 'loans/admin_loan_detail.html', context)


# -----------------------------
# Disburse Loan (Admin Only)
# -----------------------------
@user_passes_test(lambda u: u.is_staff or getattr(u, "is_admin", False))
def disburse_view(request, application_id):
    loan = get_object_or_404(LoanApplication, application_id=application_id)
    if loan.status == 'APPROVED':
        credited = loan.disburse()
        if credited:
            messages.success(
                request,
                f"Loan {loan.application_id} disbursed — ₹{loan.loan_amount} credited to the customer's account."
            )
        else:
            messages.warning(
                request,
                f"Loan {loan.application_id} marked disbursed, but the customer has no approved "
                "bank account to credit — nothing was added to their balance."
            )
    else:
        messages.error(request, "Loan cannot be disbursed unless approved.")
    return redirect('admin_dashboard:dashboard')


# -----------------------------
# Approve Loan (Admin Only)
# -----------------------------
# Standard rejection reasons shown in admin dropdown
LOAN_REJECTION_REASONS = [
    'Credit score below minimum threshold (650)',
    'Debt-to-income ratio too high (>60%)',
    'Insufficient monthly income for requested EMI',
    'Existing EMI obligations too high',
    'Incomplete or inconsistent application details',
    'Loan amount exceeds eligibility limit',
    'Requested tenure outside permissible range',
    'Applicant does not meet minimum age requirement',
    'KYC verification pending or failed',
    'Previous loan default on record',
    'Other — see custom reason',
]


@user_passes_test(lambda u: u.is_staff or getattr(u, "is_admin", False))
def approve_loan_view(request, application_id):
    from admin_dashboard.models import Notification
    from django.http import JsonResponse as JR
    loan = get_object_or_404(LoanApplication, application_id=application_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve' and loan.status == 'PENDING':
            loan.evaluate()
            loan.save()
            if loan.status == 'APPROVED':
                msg = f'Loan {loan.application_id} approved.'
                messages.success(request, msg)
                Notification.objects.create(
                    recipient=loan.user,
                    preset='loan_approved',
                    title='Loan Application Approved 💰',
                    body=(
                        f'Congratulations {loan.user.first_name or loan.user.username}! '
                        f'Your {loan.get_loan_type_display()} application '
                        f'({loan.application_id}) for ₹{loan.loan_amount:,.0f} has been approved. '
                        f'Monthly EMI: ₹{loan.emi_amount:,.0f} for {loan.tenure_months} months '
                        f'at {loan.interest_rate}% p.a. Disbursement will follow shortly.'
                    ),
                    icon='bi-cash-coin',
                )
                if is_ajax:
                    return JR({'status': 'approved', 'message': msg,
                               'application_id': application_id,
                               'new_status': 'APPROVED'})
            else:
                msg = f'Loan {loan.application_id} rejected after eligibility check: {loan.decision_reason}'
                messages.warning(request, msg)
                Notification.objects.create(
                    recipient=loan.user,
                    preset='loan_rejected',
                    title='Loan Application Update',
                    body=(
                        f'Your {loan.get_loan_type_display()} application '
                        f'({loan.application_id}) for ₹{loan.loan_amount:,.0f} could not be approved. '
                        f'Reason: {loan.decision_reason}. '
                        'You may re-apply after improving your score or contact support.'
                    ),
                    icon='bi-file-x',
                )
                if is_ajax:
                    return JR({'status': 'rejected', 'message': msg,
                               'application_id': application_id,
                               'new_status': 'REJECTED'})

        elif action == 'reject' and loan.status == 'PENDING':
            # Reason comes from dropdown; if "Other" is selected, use custom_reason field
            selected = request.POST.get('reject_reason', '').strip()
            custom   = request.POST.get('custom_reason', '').strip()
            reason   = custom if selected == 'Other — see custom reason' and custom else selected
            if not reason:
                reason = 'Rejected by admin.'
            loan.status = 'REJECTED'
            loan.decision_reason = reason
            loan.save()
            msg = f'Loan {loan.application_id} rejected: {reason}'
            messages.warning(request, msg)
            Notification.objects.create(
                recipient=loan.user,
                preset='loan_rejected',
                title='Loan Application Update',
                body=(
                    f'Your {loan.get_loan_type_display()} application ({loan.application_id}) '
                    f'for ₹{loan.loan_amount:,.0f} was not approved. '
                    f'Reason: {reason}. '
                    'Please contact support if you have questions.'
                ),
                icon='bi-file-x',
            )
            # Auto-send referral message alongside rejection
            Notification.objects.create(
                recipient=loan.user,
                preset='referral',
                title='Refer a Friend & Earn ₹500 🤝',
                body=(
                    "While we couldn't approve your loan this time, our referral programme "
                    "rewards you ₹500 for every friend who opens a SpendSmart account. "
                    "Share your referral link from your profile and start earning today!"
                ),
                icon='bi-gift',
            )
            if is_ajax:
                return JR({'status': 'rejected', 'message': msg,
                           'application_id': application_id,
                           'new_status': 'REJECTED'})

    return redirect('admin_dashboard:dashboard')


# -----------------------------
# Make EMI Repayment
# -----------------------------
@login_required
def repay_view(request, application_id):
    loan = get_object_or_404(LoanApplication, application_id=application_id, user=request.user)
    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '0')
        pin = request.POST.get('pin', '').strip()

        try:
            amount = Decimal(amount_raw)
        except Exception:
            messages.error(request, "Enter a valid repayment amount.")
            return redirect('loans:loan_detail', application_id=application_id)

        if loan.status != 'DISBURSED':
            messages.error(request, "Loan is not active for repayment.")
        elif amount <= 0:
            messages.error(request, "Repayment amount must be positive.")
        elif request.user.is_pin_locked():
            messages.error(request, "Too many incorrect PIN attempts. Please try again in a few minutes.")
        elif not request.user.pin_hash:
            messages.error(request, "You haven't set a transaction PIN yet. Set one from your profile first.")
        elif not request.user.check_transaction_pin(pin):
            request.user.register_failed_pin()
            messages.error(request, "Incorrect transaction PIN.")
        else:
            request.user.reset_pin_attempts()
            loan.make_repayment(amount)
            if loan.status == 'CLOSED':
                messages.success(request, f"Loan {loan.application_id} fully repaid and closed.")
            else:
                messages.success(request, f"Repayment of ₹{amount} recorded for Loan {loan.application_id}.")
        return redirect('loans:loan_detail', application_id=application_id)

    return render(request, 'loans/repay.html', {'loan': loan})