from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404

from .forms import LoanApplicationForm
from .models import LoanApplication


# -----------------------------
# Apply for Loan
# -----------------------------
@login_required
def apply_view(request):
    if request.method == 'POST':
        # tenure_months comes from the hidden field set by JS (years * 12).
        # If the user never triggered the years input event the hidden field
        # is empty, so we coerce it here before form validation runs.
        post_data = request.POST.copy()
        tenure_raw = post_data.get('tenure_months', '').strip()
        if not tenure_raw:
            # fall back to the years field if present
            years_raw = post_data.get('tenure_years', '').strip()
            if years_raw.isdigit() and int(years_raw) > 0:
                post_data['tenure_months'] = str(int(years_raw) * 12)
        form = LoanApplicationForm(post_data)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.evaluate()   # computes EMI, DTI, eligibility flags; sets PENDING
            application.save()
            messages.success(
                request,
                f"Application {application.application_id} submitted successfully. "
                f"Our team will review it and update you shortly."
            )
            return redirect('loans:loan_detail', application_id=application.application_id)
    else:
        form = LoanApplicationForm()
    return render(request, 'loans/apply.html', {'form': form})


# -----------------------------
# My Loans
# -----------------------------
@login_required
def my_loans_view(request):
    loans = request.user.loan_applications.all()
    return render(request, 'loans/my_loans.html', {'loans': loans})


# -----------------------------
# Loan Detail
# -----------------------------
@login_required
def loan_detail_view(request, application_id):
    loan = get_object_or_404(LoanApplication, application_id=application_id, user=request.user)
    schedule = loan.amortization_schedule() if loan.status in ['APPROVED', 'DISBURSED'] else []
    total_interest = sum(row['interest'] for row in schedule) if schedule else 0
    return render(request, 'loans/loan_detail.html', {
        'loan': loan,
        'schedule': schedule,
        'total_interest': round(total_interest, 2),
    })


# -----------------------------
# Disburse Loan (Admin Only)
# -----------------------------
@user_passes_test(lambda u: u.is_staff or getattr(u, "is_admin", False))
def disburse_view(request, application_id):
    loan = get_object_or_404(LoanApplication, application_id=application_id)
    if loan.status == 'APPROVED':
        loan.disburse()
        messages.success(request, f"Loan {loan.application_id} disbursed successfully.")
    else:
        messages.error(request, "Loan cannot be disbursed unless approved.")
    return redirect('loans:loan_detail', application_id=application_id)


# -----------------------------
# Make EMI Repayment
# -----------------------------
@login_required
def repay_view(request, application_id):
    loan = get_object_or_404(LoanApplication, application_id=application_id, user=request.user)
    if request.method == 'POST':
        amount_raw = request.POST.get('amount', '0')
        try:
            amount = Decimal(amount_raw)
        except Exception:
            messages.error(request, "Enter a valid repayment amount.")
            return redirect('loans:loan_detail', application_id=application_id)

        if loan.status != 'DISBURSED':
            messages.error(request, "Loan is not active for repayment.")
        elif amount <= 0:
            messages.error(request, "Repayment amount must be positive.")
        else:
            loan.make_repayment(amount)
            if loan.status == 'CLOSED':
                messages.success(request, f"Loan {loan.application_id} fully repaid and closed.")
            else:
                messages.success(request, f"Repayment of ₹{amount} recorded for Loan {loan.application_id}.")
        return redirect('loans:loan_detail', application_id=application_id)

    return render(request, 'loans/repay.html', {'loan': loan})

# -----------------------------
# Approve Loan (Admin Only)
# -----------------------------
@user_passes_test(lambda u: u.is_staff or getattr(u, "is_admin", False))
def approve_loan_view(request, application_id):
    from django.utils import timezone
    loan = get_object_or_404(LoanApplication, application_id=application_id)
    if request.method == 'POST':
        if loan.status == 'PENDING':
            loan.status = 'APPROVED'
            loan.decision_reason = request.POST.get('note', 'Approved by admin.')
            loan.decided_at = timezone.now()
            loan.save(update_fields=['status', 'decision_reason', 'decided_at'])
            messages.success(request, f"Loan {loan.application_id} approved.")
        else:
            messages.error(request, "Loan is not in PENDING state.")
    return redirect('admin_dashboard:dashboard')


# -----------------------------
# Reject Loan (Admin Only)
# -----------------------------
@user_passes_test(lambda u: u.is_staff or getattr(u, "is_admin", False))
def reject_loan_view(request, application_id):
    from django.utils import timezone
    loan = get_object_or_404(LoanApplication, application_id=application_id)
    if request.method == 'POST':
        if loan.status == 'PENDING':
            reason = request.POST.get('reason', 'Rejected by admin.').strip()
            loan.status = 'REJECTED'
            loan.decision_reason = reason
            loan.decided_at = timezone.now()
            loan.save(update_fields=['status', 'decision_reason', 'decided_at'])
            messages.success(request, f"Loan {loan.application_id} rejected.")
        else:
            messages.error(request, "Loan is not in PENDING state.")
    return redirect('admin_dashboard:dashboard')
