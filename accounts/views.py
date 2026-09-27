from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
import re

from .forms import RegisterForm, SetPinForm, AdminRegisterForm
from .models import CustomUser
from upi.models import BankAccount

MAX_LOGIN_ATTEMPTS   = 3
LOGIN_LOCKOUT_MINUTES = 5

PIN_RE = re.compile(r'^\d{4}$')  # PIN is exactly 4 digits, per set_pin.html


def _notify_pin_changed(user):
    """
    Best-effort security notification. Wrapped in try/except so a missing
    or differently-shaped Notification model can never block a PIN change —
    worst case the user just doesn't get the bell alert.
    """
    try:
        from admin_dashboard.models import Notification
        Notification.objects.create(
            recipient=user,
            title="Transaction PIN changed",
            body="Your transaction PIN was changed successfully. If this wasn't you, contact support immediately.",
            icon="bi-shield-lock",
            category='ACCOUNT',
            is_important=True,
        )
    except Exception:
        pass


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
            initial_balance = form.cleaned_data.get('initial_balance', 0)
            BankAccount.objects.create(
                user=user,
                account_type='SAVINGS',
                balance=0,
                requested_balance=initial_balance,
                is_approved=False,
            )
            auth_login(request, user)
            messages.success(
                request,
                "Welcome! Your account is pending admin approval. "
                "Once approved, your initial deposit will be credited."
            )
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
# Set Transaction PIN (first-time set, right after registration).
# Also captures the security question + answer in the SAME form,
# so it's ready to use the first time Forgot PIN is ever needed.
# ─────────────────────────────────────────────
@login_required
def set_pin_view(request):
    error = None
    if request.method == 'POST':
        form = SetPinForm(request.POST)
        question = request.POST.get('security_question', '')
        answer   = request.POST.get('security_answer', '').strip()
        valid_keys = dict(CustomUser.SECURITY_QUESTIONS)

        if form.is_valid():
            if question not in valid_keys:
                error = "Please choose a valid security question."
            elif len(answer) < 2:
                error = "Your security answer is too short."
            else:
                request.user.set_transaction_pin(form.cleaned_data['pin'])
                request.user.reset_pin_attempts()
                request.user.security_question = question
                request.user.set_security_answer(answer)
                request.user.save()
                messages.success(request, "Transaction PIN set successfully.")
                return redirect('upi:dashboard')
    else:
        form = SetPinForm()
    return render(request, 'accounts/set_pin.html', {
        'form': form,
        'error': error,
        'security_questions': CustomUser.SECURITY_QUESTIONS,
    })


# ─────────────────────────────────────────────
# Change Transaction PIN — knows current PIN
# Same 3-attempt / 5-min lockout as Send Money / Add Money, via the
# model's existing is_pin_locked() / register_failed_pin() / reset_pin_attempts().
# ─────────────────────────────────────────────
@login_required
def change_pin_view(request):
    user = request.user
    error = None

    if user.is_pin_locked():
        remaining = int((user.pin_locked_until - timezone.now()).total_seconds() // 60) + 1
        messages.error(request, f"Too many failed PIN attempts. Try again in {remaining} minute(s).")
        return render(request, 'accounts/change_pin.html', {'locked': True, 'remaining': remaining})

    if request.method == 'POST':
        current_pin = request.POST.get('current_pin', '').strip()
        new_pin     = request.POST.get('new_pin', '').strip()
        confirm_pin = request.POST.get('confirm_pin', '').strip()

        if not user.check_transaction_pin(current_pin):
            user.register_failed_pin()
            if user.is_pin_locked():
                error = f"Too many failed attempts. PIN changes locked for {user.PIN_LOCKOUT_MINUTES} minutes."
            else:
                remaining_attempts = user.MAX_PIN_ATTEMPTS - user.failed_pin_attempts
                error = f"Incorrect current PIN. {remaining_attempts} attempt(s) remaining."
        elif not PIN_RE.match(new_pin):
            error = "New PIN must be exactly 4 digits."
        elif new_pin != confirm_pin:
            error = "New PIN and confirmation do not match."
        elif new_pin == current_pin:
            error = "New PIN must be different from your current PIN."
        else:
            user.set_transaction_pin(new_pin)
            user.reset_pin_attempts()
            user.save()
            _notify_pin_changed(user)
            messages.success(request, "Transaction PIN updated successfully.")
            return redirect('accounts:profile')

    return render(request, 'accounts/change_pin.html', {'error': error, 'locked': False})


# ─────────────────────────────────────────────
# Forgot Transaction PIN — doesn't know current PIN.
# Demo-appropriate flow: re-authenticate with account password (no email/SMS
# sending in this project), PLUS the user's own security question if they've
# set one — two independent identity checks instead of one. Falls back to
# password-only for accounts that haven't set a security question yet.
# Reuses the same failed_pin_attempts/pin_locked_until fields, so repeated
# wrong guesses on either check still lock out after MAX_PIN_ATTEMPTS.
# ─────────────────────────────────────────────
@login_required
def forgot_pin_view(request):
    from django.utils.http import url_has_allowed_host_and_scheme

    user = request.user
    error = None
    has_sq = user.has_security_question()

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if next_url and not url_has_allowed_host_and_scheme(
        url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = ''
    safe_next = next_url or 'accounts:profile'

    # ── Identity check is the security question ONLY — there is no
    #    separate login-password step in this flow. If the user never
    #    set a security question, they can't self-serve a reset here;
    #    send them to set one first (once they're back in, via the PIN
    #    they still remember, or an admin-assisted path outside this view).
    if not has_sq:
        messages.warning(
            request,
            "You haven't set a security question yet, so we can't verify "
            "your identity to reset your PIN this way. Set one up first."
        )
        return redirect('accounts:set_security_question')

    if user.is_pin_locked():
        remaining = int((user.pin_locked_until - timezone.now()).total_seconds() // 60) + 1
        messages.error(request, f"Too many failed attempts. Try again in {remaining} minute(s).")
        return render(request, 'accounts/forgot_pin.html', {
            'locked': True, 'remaining': remaining, 'has_sq': has_sq, 'next': next_url,
        })

    if request.method == 'POST':
        sec_answer   = request.POST.get('security_answer', '').strip()
        new_pin      = request.POST.get('new_pin', '').strip()
        confirm_pin  = request.POST.get('confirm_pin', '').strip()

        # ── Identity check: security question only (no login password step) ──
        if not user.check_security_answer(sec_answer):
            user.register_failed_pin()
            if user.is_pin_locked():
                error = f"Too many failed attempts. PIN reset locked for {user.PIN_LOCKOUT_MINUTES} minutes."
            else:
                remaining_attempts = user.MAX_PIN_ATTEMPTS - user.failed_pin_attempts
                error = f"Incorrect answer to your security question. {remaining_attempts} attempt(s) remaining."
        elif not PIN_RE.match(new_pin):
            error = "New PIN must be exactly 4 digits."
        elif new_pin != confirm_pin:
            error = "New PIN and confirmation do not match."
        else:
            user.set_transaction_pin(new_pin)
            user.reset_pin_attempts()
            user.save()
            _notify_pin_changed(user)
            messages.success(request, "Transaction PIN reset successfully.")
            if next_url:
                return redirect(safe_next)
            return redirect('accounts:profile')

    return render(request, 'accounts/forgot_pin.html', {
        'error': error,
        'locked': False,
        'has_sq': has_sq,
        'security_question': user.get_security_question_display() if has_sq else None,
        'next': next_url,
    })


# ─────────────────────────────────────────────
# Set / Update Security Question — PIN-gated
# For existing accounts created before this feature existed (already have
# a PIN, never captured a security question). Not a wide-open way to
# overwrite someone's identity-recovery answer — requires the current PIN.
# ─────────────────────────────────────────────
@login_required
def set_security_question_view(request):
    user = request.user
    error = None

    if user.is_pin_locked():
        remaining = int((user.pin_locked_until - timezone.now()).total_seconds() // 60) + 1
        messages.error(request, f"Too many failed PIN attempts. Try again in {remaining} minute(s).")
        return render(request, 'accounts/set_security_question.html', {
            'locked': True, 'remaining': remaining,
            'questions': CustomUser.SECURITY_QUESTIONS,
            'current_question': user.security_question,
        })

    if request.method == 'POST':
        current_pin = request.POST.get('current_pin', '').strip()
        question    = request.POST.get('security_question', '').strip()
        answer      = request.POST.get('security_answer', '').strip()
        valid_keys  = dict(CustomUser.SECURITY_QUESTIONS)

        if not user.check_transaction_pin(current_pin):
            user.register_failed_pin()
            if user.is_pin_locked():
                error = f"Too many failed attempts. Try again in {user.PIN_LOCKOUT_MINUTES} minutes."
            else:
                remaining_attempts = user.MAX_PIN_ATTEMPTS - user.failed_pin_attempts
                error = f"Incorrect PIN. {remaining_attempts} attempt(s) remaining."
        elif question not in valid_keys:
            error = "Please choose a valid security question."
        elif len(answer) < 2:
            error = "Your security answer is too short."
        else:
            user.reset_pin_attempts()
            user.security_question = question
            user.set_security_answer(answer)
            user.save(update_fields=['security_question', 'security_answer_hash'])
            messages.success(request, "Security question saved.")
            return redirect('accounts:profile')

    return render(request, 'accounts/set_security_question.html', {
        'error': error,
        'locked': False,
        'questions': CustomUser.SECURITY_QUESTIONS,
        'current_question': user.security_question,
    })


# ─────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────
@login_required
def profile_view(request):
    accounts = request.user.accounts.all()

    # Sum balances of approved accounts only.
    # aggregate() returns None when no rows match, so we fall back to Decimal 0.
    total_balance = (
        accounts
        .filter(is_approved=True)
        .aggregate(total=Sum('balance'))['total']
    ) or Decimal('0.00')

    return render(request, 'accounts/profile.html', {
        'accounts'      : accounts,
        'total_balance' : total_balance,
    })


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