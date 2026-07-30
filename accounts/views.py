from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect

from .forms import RegisterForm, SetPinForm
from upi.models import BankAccount


def register_view(request):
    if request.user.is_authenticated:
        return redirect('upi:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Auto-create a savings account with a welcome bonus balance (simulation)
            BankAccount.objects.create(user=user, account_type='SAVINGS')
            auth_login(request, user)
            messages.success(request, "Welcome to SpendSmart Bank! Your account has been created.")
            return redirect('accounts:set_pin')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def set_pin_view(request):
    if request.method == 'POST':
        form = SetPinForm(request.POST)
        if form.is_valid():
            request.user.set_transaction_pin(form.cleaned_data['pin'])
            request.user.save()
            messages.success(request, "Transaction PIN set successfully.")
            return redirect('upi:dashboard')
    else:
        form = SetPinForm()
    return render(request, 'accounts/set_pin.html', {'form': form})


@login_required
def profile_view(request):
    accounts = request.user.accounts.all()
    return render(request, 'accounts/profile.html', {'accounts': accounts})
