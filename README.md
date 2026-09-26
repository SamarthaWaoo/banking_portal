# SpendSmart Bank — Notification System Patch

## Where each file goes

| File in this zip                     | Destination                                  | Type |
|---------------------------------------|-----------------------------------------------|------|
| admin_dashboard/models.py             | `admin_dashboard/models.py`                   | FULL REPLACE |
| admin_dashboard/views.py              | `admin_dashboard/views.py`                    | FULL REPLACE |
| admin_dashboard/context_processors.py | `admin_dashboard/context_processors.py`       | NEW FILE |
| loans/views.py                        | `loans/views.py`                              | FULL REPLACE |
| accounts/views.py                     | `accounts/views.py`                           | FULL REPLACE |
| upi/views_PATCH.py                    | merge into `upi/views.py`                     | **PATCH ONLY — see below** |
| upi/urls.py                           | `upi/urls.py`                                 | FULL REPLACE |
| templates/dashboard.html              | `upi/templates/upi/dashboard.html`            | FULL REPLACE |
| templates/base.html                   | `templates/base.html`                         | FULL REPLACE |
| templates/my_loans.html               | `loans/templates/loans/my_loans.html`         | FULL REPLACE |

## ⚠️ IMPORTANT — upi/views.py is a PATCH, not a full file

I could not see the full body of your `send_money_view` (part of it was
truncated when I read the file), so I did **not** regenerate that function —
doing so from a partial view risked silently corrupting your money-transfer
logic. `upi/views_PATCH.py` contains only:

- `dashboard_view` (replace)
- `add_amount_view` (replace)
- `mark_notifications_read` (add, new)
- the one new import line

Open your real `upi/views.py`, replace those two functions with the patched
versions, add the import, and append the new function at the bottom. Leave
everything else (`search_users`, `get_all_users`, `send_money_view`,
`transaction_history_view`, `download_statement`, `add_beneficiary`,
`remove_beneficiary`) exactly as it is.

## Settings change required

In `settings.py`, add the new context processor so the top-bar bell works on
every page:

```python
TEMPLATES = [
    {
        ...
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'admin_dashboard.context_processors.notification_count',  # ADD THIS
            ],
        },
    },
]
```

## Migration

The `Notification` model gained two new fields (`category`, `is_important`).
After copying `admin_dashboard/models.py` in:

```bash
python manage.py makemigrations admin_dashboard
python manage.py migrate
```

Existing rows will default to `category='ACCOUNT'`, `is_important=False` —
fine, since old notifications predate this feature.

## What changed, behaviorally

1. **Add Money now asks for the transaction PIN** and verifies it against
   `CustomUser.check_transaction_pin()` — same lockout rules as Send Money
   (3 wrong attempts → 5 min lock).
2. **Top-bar bell** (in `base.html`) shows ALL notifications for the logged-in
   customer with an unread-count badge; opening it marks them read.
3. **Customer dashboard** no longer shows the full notification feed — only
   an `is_important=True` green box (account creation, salary/account
   approval credit, EMI due).
4. **Loans → My Loans page** shows only `category='LOAN'` notifications
   (approved / rejected / disbursed / EMI debited / EMI due) — nothing
   promotional.
5. **Auto-sent notifications** now fire from:
   - `accounts/views.py::register_view` → welcome
   - `admin_dashboard/views.py::approve_account_view` → account approved + credited (important)
   - `loans/views.py::approve_loan_view` → loan approved / rejected
   - `loans/views.py::disburse_view` → loan disbursed
   - `loans/views.py::repay_view` → EMI debited
6. **Promotional/common messages** (festival offers, rate updates, referral)
   sent by admins via the messaging tab keep `category='PROMO'` automatically
   (via `Notification.PRESET_META`) and only ever appear in the bell — never
   in the green box or the Loans page.

## Not yet wired: "Next EMI due" reminders

There's no scheduled job in your codebase to detect upcoming due dates.
`Notification.notify(..., 'loan_due', ...)` is ready to use — you'd call it
from a management command (e.g. `python manage.py send_emi_reminders`) run
via cron/Celery-beat, checking each `DISBURSED` loan's next due date. Let me
know if you want that command written.
