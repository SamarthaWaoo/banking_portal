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
            # Explicitly create the BankAccount here — more reliable than a signal.
            BankAccount.objects.create(user=user, account_type='SAVINGS')
            auth_login(request, user)
            messages.success(request, "Welcome to SpendSmart Bank! Your savings account is ready.")
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
            request.user.reset_pin_attempts()   # clear any stale lock on PIN change
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
