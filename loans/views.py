from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import LoanApplicationForm
from .models import LoanApplication


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


@login_required
def my_loans_view(request):
    loans = request.user.loan_applications.all()
    return render(request, 'loans/my_loans.html', {'loans': loans})


@login_required
def loan_detail_view(request, application_id):
    loan = get_object_or_404(LoanApplication, application_id=application_id, user=request.user)
    schedule = loan.amortization_schedule() if loan.status == 'APPROVED' else []
    total_interest = sum(row['interest'] for row in schedule) if schedule else 0
    return render(request, 'loans/loan_detail.html', {
        'loan': loan, 'schedule': schedule, 'total_interest': round(total_interest, 2),
    })
