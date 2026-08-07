from django.shortcuts import render

# Create your views here.
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from accounts.models import CustomUser, Account
from upi.models import Transaction
from loans.models import LoanApplication

# Only allow admin users
def admin_required(view_func):
    return user_passes_test(lambda u: u.is_admin)(view_func)

@login_required
@admin_required
def dashboard_view(request):
    users = CustomUser.objects.all()
    accounts = Account.objects.all()
    transactions = Transaction.objects.all()[:50]  # latest 50
    loans = LoanApplication.objects.all()

    return render(request, "admin_dashboard/dashboard.html", {
        "users": users,
        "accounts": accounts,
        "transactions": transactions,
        "loans": loans,
    })
