from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import RegisterForm, SetPinForm, AdminRegisterForm
from .models import CustomUser
from upi.models import BankAccount

MAX_LOGIN_ATTEMPTS   = 3
LOGIN_LOCKOUT_MINUTES = 5

# ─────────────────────────────────────────────
# Customer Registration
# ─────────────────────────────────────────────
def register_view(request):
    if request.user.is_authenticated:
        return redirect('upi:dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            BankAccount.objects.create(user=user, account_type='SAVINGS')
            auth_login(request, user)
            messages.success(request, "Welcome! Your savings account is ready. Set your transaction PIN below.")
            return redirect('accounts:set_pin')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


# ─────────────────────────────────────────────
# Customer Login — 3-attempt lockout
# ─────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('upi:dashboard')

    error    = None
    locked   = False
    lock_msg = None

    # Carry failed-attempt counter in session (no DB hit before login)
    attempts = request.session.get('login_attempts', 0)
    locked_until = request.session.get('login_locked_until')

    # Check if currently locked
    if locked_until:
        from datetime import datetime
        locked_until_dt = datetime.fromisoformat(locked_until)
        if timezone.now() < timezone.make_aware(locked_until_dt.replace(tzinfo=None), timezone.get_current_timezone()) \
                if locked_until_dt.tzinfo is None else timezone.now() < locked_until_dt:
            locked = True
            remaining = int((locked_until_dt - timezone.now().replace(tzinfo=None)).total_seconds() // 60) + 1 \
                if locked_until_dt.tzinfo is None else \
                int((locked_until_dt - timezone.now()).total_seconds() // 60) + 1
            lock_msg = f"Too many failed attempts. Account locked for {remaining} more minute(s)."
        else:
            # Lock expired — reset
            request.session['login_attempts'] = 0
            request.session['login_locked_until'] = None
            attempts = 0
            locked_until = None

    if request.method == 'POST' and not locked:
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Successful — clear counters and log in
            request.session['login_attempts'] = 0
            request.session['login_locked_until'] = None
            auth_login(request, user)
            # Admins who log in via the customer login page → admin dashboard
            if user.is_staff or getattr(user, 'is_admin', False):
                return redirect('admin_dashboard:dashboard')
            return redirect('upi:dashboard')
        else:
            attempts += 1
            request.session['login_attempts'] = attempts
            remaining_attempts = MAX_LOGIN_ATTEMPTS - attempts
            if attempts >= MAX_LOGIN_ATTEMPTS:
                lock_time = timezone.now() + timezone.timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
                request.session['login_locked_until'] = lock_time.isoformat()
                locked = True
                lock_msg = (
                    f"Too many failed attempts. Your login is locked for "
                    f"{LOGIN_LOCKOUT_MINUTES} minutes."
                )
                error = lock_msg
            else:
                error = f"Incorrect username or password. {remaining_attempts} attempt(s) remaining before lockout."

    return render(request, 'accounts/login.html', {
        'error': error,
        'locked': locked,
        'lock_msg': lock_msg,
        'attempts': attempts,
        'max_attempts': MAX_LOGIN_ATTEMPTS,
    })


# ─────────────────────────────────────────────
# Logout
# ─────────────────────────────────────────────
def logout_view(request):
    if request.method == 'POST':
        auth_logout(request)
    return redirect('landing')


# ─────────────────────────────────────────────
# Set Transaction PIN
# ─────────────────────────────────────────────
@login_required
def set_pin_view(request):
    if request.method == 'POST':
        form = SetPinForm(request.POST)
        if form.is_valid():
            request.user.set_transaction_pin(form.cleaned_data['pin'])
            request.user.reset_pin_attempts()
            request.user.save()
            messages.success(request, "Transaction PIN set successfully.")
            return redirect('upi:dashboard')
    else:
        form = SetPinForm()
    return render(request, 'accounts/set_pin.html', {'form': form})


# ─────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────
@login_required
def profile_view(request):
    accounts = request.user.accounts.all()
    return render(request, 'accounts/profile.html', {'accounts': accounts})


# ─────────────────────────────────────────────
# Admin Registration (separate from customer)
# ─────────────────────────────────────────────
def admin_register_view(request):
    # Only allow if no admin exists yet, or if request comes from an existing admin
    if request.user.is_authenticated and not (request.user.is_staff or request.user.is_admin):
        return redirect('upi:dashboard')

    if request.method == 'POST':
        form = AdminRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True
            user.is_admin = True
            user.is_superuser = True
            user.save()
            messages.success(request, f"Admin account '{user.username}' created successfully.")
            return redirect('accounts:admin_login')
    else:
        form = AdminRegisterForm()
    return render(request, 'accounts/admin_register.html', {'form': form})


# ─────────────────────────────────────────────
# Admin Login (separate page, redirects to admin dashboard)
# ─────────────────────────────────────────────
def admin_login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_admin:
            return redirect('admin_dashboard:dashboard')
        return redirect('upi:dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None and (user.is_staff or user.is_admin):
            auth_login(request, user)
            return redirect('admin_dashboard:dashboard')
        elif user is not None:
            error = "This account does not have admin privileges."
        else:
            error = "Invalid credentials."

    return render(request, 'accounts/admin_login.html', {'error': error})
