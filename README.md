# SpendSmart Bank

A Django-based simulated retail banking platform — customer accounts, UPI-style
money transfers, loans, budgeting, and a staff-facing admin console — built
for demo/learning purposes.

---

## Apps

| App               | Responsibility                                                        |
|--------------------|------------------------------------------------------------------------|
| `accounts`         | Registration, login, `CustomUser` model, transaction PIN handling      |
| `upi`              | Customer dashboard, send/receive money, beneficiaries, statements      |
| `loans`            | Loan applications, approval workflow, disbursement, EMI repayment      |
| `admin_dashboard`  | Staff console — users, accounts, transactions, loans, audit, messaging |

Shared templates (`base.html`, design tokens, components) live under
`templates/` and `static/css/style.css`.

---

## Key features

### Customer side
- Register → pending account approval → admin credits requested deposit
- Send money via UPI ID, with a transaction PIN (3 wrong attempts → 5 min lock)
- Add Money now also requires the transaction PIN, same lockout rules as Send Money
- Beneficiaries, transaction history, downloadable statements (incl. XBRL export)
- Loan application, tracked through Pending → Approved/Rejected → Disbursed
- Budgets with progress bars (ok / warning / over)
- Top-bar notification bell — shows **all** notifications for the logged-in
  customer with an unread-count badge; opening it marks them read
- Dashboard itself only surfaces `is_important=True` notifications (account
  creation, approval + credit, EMI due) in a green highlight box — the bell
  is the full feed
- My Loans page shows only `category='LOAN'` notifications (approved /
  rejected / disbursed / EMI debited / EMI due) — no promo noise

### Admin console
Single-page "rail" layout — icon-only sidebar, tabbed main pane, all inside
one bordered shell:

- **Users** — full list, live client-side username search
- **Accounts** — balances, freeze/unfreeze, XBRL export
- **Pending** — approve (credits requested deposit) / reject new account
  requests, plus a rejected-accounts log
- **Transactions** — paginated ledger with status + flagged/resolved badges
- **Failed** — unresolved failed transactions with a resolution-note workflow
- **Loans** — review pending applications, disburse approved ones
- **Messaging** — send notifications (broadcast or single customer) from
  preset templates or a custom message; recent-notifications history
- **Audit Log** — last 40 operations across all users
- **Charts** — transaction status + loan status breakdowns (Chart.js)

KPI stat strip (users / accounts / pending / loans / success / failed /
total balance / flagged count) sits above the tab content as bordered stat
chips.

**Layout note:** the rail does *not* use `position: fixed` — something in
the base template sets a `transform`/`filter`/`will-change` on an ancestor,
which breaks fixed positioning. Instead `.vb-admin-shell` is a fixed-height
flex container; the rail and the tab pane both scroll internally within it.

---

## Notification system

`Notification` model fields: `recipient` (nullable = broadcast), `title`,
`body`, `icon`, `category` (`ACCOUNT` / `LOAN` / `PROMO`), `is_important`,
`created_at`, `read_at`.

Preset templates (`Notification.PRESET_META`) map each messaging-tab preset
to a category automatically — festival offers / rate updates / referral
always land as `PROMO` and only ever show in the bell, never on the
dashboard or Loans page.

**Auto-sent from:**

| Trigger                                   | Source                                      |
|---------------------------------------------|----------------------------------------------|
| Welcome                                    | `accounts/views.py::register_view`            |
| Account approved + credited (important)    | `admin_dashboard/views.py::approve_account_view` |
| Loan approved / rejected                   | `loans/views.py::approve_loan_view`            |
| Loan disbursed                             | `loans/views.py::disburse_view`                |
| EMI debited                                | `loans/views.py::repay_view`                   |

**Not yet wired:** EMI *due-soon* reminders. `Notification.notify(...,
'loan_due', ...)` is ready to call, but there's no scheduled job yet —
would need a management command (e.g. `send_emi_reminders`) run via
cron/Celery-beat, checking each `DISBURSED` loan's upcoming due date.

---

## Setup

```bash
pip install -r requirements.txt

# settings.py must include the notification-count context processor
# so the top-bar bell badge works on every page:
#   admin_dashboard.context_processors.notification_count

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser   # or mark a user is_staff/is_admin
python manage.py runserver
```

---

## Design system

CSS custom properties in `static/css/style.css` (`:root`) drive the whole
UI — purple primary (`--vb-navy: #7C3AED`), enterprise off-white background,
consistent radii/shadows/font-size scale. Three distinct shells share the
tokens but are visually separate:

- **Public/marketing** — light navbar, gradient hero, feature cards
- **Customer app** — dark fixed sidebar (`.vb-sidebar`) + topbar, off-canvas
  on mobile
- **Admin console** — dark icon rail (`.vb-admin-rail`) + KPI strip + tabs,
  internal-scroll shell (see layout note above)

---

## Known limitations

- EMI due-date reminders are not scheduled (see above)
- `upi/views.py::send_money_view` was patched around, not regenerated, to
  avoid corrupting existing transfer logic from a partially-read file —
  worth a full review pass when convenient