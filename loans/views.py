from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
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
        form = LoanApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.user = request.user
            application.save()  # sets interest_rate via model save()
            application.evaluate()
            application.save()
            if application.status == 'APPROVED':
                messages.success(request, f"Congratulations! Loan {application.application_id} approved.")
            else:
                messages.warning(request, f"Loan {application.application_id} was not approved this time.")
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
        'loan': loan, 'schedule': schedule, 'total_interest': round(total_interest, 2),
    })


# -----------------------------
# Disburse Loan (Admin/Simulation)
# -----------------------------
@login_required
def disburse_view(request, application_id):
    loan = get_object_or_404(LoanApplication, application_id=application_id, user=request.user)
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
