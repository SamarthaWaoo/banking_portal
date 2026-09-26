# SpendSmart Bank — UI Overhaul + Spending Insights, Budgets & PDF Statements

This zip contains **only the files that changed**, across two rounds of
work. Every path inside the zip mirrors its location in your project root —
unzip directly into your project root, overwriting.

## Files in this patch

| File                                                | Type          |
|------------------------------------------------------|---------------|
| `templates/base.html`                                 | FULL REPLACE  |
| `templates/landing.html`                              | FULL REPLACE  |
| `static/css/style.css`                                | FULL REPLACE  |
| `templates/upi/dashboard.html`                        | FULL REPLACE  |
| `templates/upi/send_money.html`                       | FULL REPLACE  |
| `templates/upi/transactions.html`                     | FULL REPLACE  |
| `templates/upi/budgets.html`                          | NEW FILE      |
| `templates/accounts/profile.html`                     | FULL REPLACE  |
| `templates/accounts/set_pin.html`                     | FULL REPLACE  |
| `templates/loans/my_loans.html`                       | FULL REPLACE  |
| `templates/loans/apply.html`                          | FULL REPLACE  |
| `templates/loans/loan_detail.html`                    | FULL REPLACE  |
| `upi/models.py`                                       | FULL REPLACE  |
| `upi/admin.py`                                        | FULL REPLACE  |
| `upi/views.py`                                        | FULL REPLACE  |
| `upi/urls.py`                                         | FULL REPLACE  |
| `upi/migrations/0012_transaction_category_budget.py`  | NEW FILE      |

Nothing in `accounts/models.py`, `accounts/views.py`, `loans/models.py`,
`loans/views.py`, `admin_dashboard/`, `banksuite/settings.py`, or your DB
config was touched.

## 1. Copy the files, then migrate

```bash
python manage.py makemigrations --check   # should say "No changes detected"
python manage.py migrate
```

## 2. Round 2 — what's new: enterprise UI overhaul

### Sidebar app shell (the big structural change)
- Authenticated **customers** now get a dark sidebar + slim topbar layout —
  Dashboard, Send Money, Transactions, Budgets, Loans, Profile — with active-link
  highlighting, a collapsible mobile drawer, and a user card + logout pinned
  to the bottom.
- **Staff/admin accounts and everyone logged out** (landing, login, register,
  admin login) keep the original top navbar — deliberately, so it doesn't
  collide with the admin dashboard's own internal tab UI.
- This is all driven by one condition in `base.html`
  (`user.is_authenticated and not user.is_staff and not user.is_admin`) —
  no new context processor, no settings change.

### Landing page redesign
- New dark hero section with a gradient background, a floating "product
  mockup" card (mini spending-by-category preview, pure CSS/HTML — no image
  asset needed), and a trust-signal strip.
- Feature grid restyled with icon tiles and hover elevation.
- Same URLs, same copy structure, same disclaimer — just a properly
  composed enterprise marketing layout instead of stacked default-Bootstrap
  sections.

### Design tokens
- `style.css` now defines a real token set: ink/sidebar colors, a 3-step
  radius scale, a 4-step shadow scale, and a type scale — used throughout
  the new components so future additions have something consistent to pull
  from instead of ad-hoc inline styles.

### Page titles in the topbar
- Dashboard, Send Money, Transactions, Budgets, Profile, My Loans, Apply for
  a Loan, Loan detail, and Set PIN now set `{% block page_title %}`, shown
  in the app-shell topbar.

## 3. Round 1 recap — Spending Insights, Budgets, PDFs

(Full detail was in the previous version of this README — summarized here
since those files are included again with no functional changes this round,
only the visual wrapper around them changed.)

- Every transaction now carries a **category**; Send Money has a category
  picker.
- New **Budgets** page (`/upi/budgets/`) — monthly ₹ limits per category
  with live progress bars.
- Dashboard **Spending Insights**: stat row, 6-month cash-flow chart,
  category breakdown doughnut, budget snapshot widget (Chart.js via CDN).
- **Real PDF statements** (`reportlab`, already in your `requirements.txt`)
  — fixed a bug where "Download PDF Statement" actually served XML. The XML
  export still exists at `upi:download_statement_xml`.
- Per-transaction **PDF receipts**, access-checked server-side.

## 4. Tested

Everything below was run against a local SQLite DB (`DB_ENGINE=sqlite3`)
before packaging:

- `manage.py check` — no issues, both rounds.
- `manage.py makemigrations --check --dry-run` — no drift.
- `manage.py migrate` — applies cleanly.
- Rendered every touched URL via Django's test client across **three
  roles**: anonymous, customer, and staff/admin:
  - Anonymous: `/`, `/accounts/login/`, `/accounts/register/`,
    `/accounts/admin/login/` → all 200, top navbar layout.
  - Customer: `/`, `/upi/dashboard/`, `/upi/send-money/`,
    `/upi/transactions/`, `/upi/budgets/`, `/accounts/profile/`,
    `/loans/my-loans/`, `/loans/apply/`, `/accounts/set-pin/` → all 200,
    sidebar app-shell layout, active-link highlighting confirmed on the
    Dashboard link.
  - Staff/admin: `/`, `/admin-dashboard/` → all 200, confirmed **not**
    wrapped in the sidebar (keeps the classic navbar as intended).
- Checked rendered HTML for leaked/unrendered template tags (`{%`, `{{`) on
  every page above — none found.
- Confirmed the statement PDF and a transaction receipt PDF both generate
  successfully, and that a user who isn't the sender/receiver of a
  transaction gets a 404 on that transaction's receipt URL.

## 6. Round 3 — completing the untouched parts

### Admin Operations Console
- The icon-rail + KPI-ticker + tabbed layout was already well-built
  functionally (AJAX approve/reject, live search, Chart.js panels) — this
  round gave it a visual pass rather than a rebuild:
  - The icon rail is now dark (`var(--vb-sidebar-bg)`), visually matching
    the customer sidebar so it reads as "the same product, admin mode" —
    without literally becoming a sidebar, since the existing tab system
    already does that job well.
  - The KPI ticker got real typographic hierarchy (uppercase micro-labels,
    consistent number weight) instead of ad-hoc inline-styled spans.
  - Cards/tables inside the admin body now use the same radius/shadow
    tokens as everywhere else, and lost the "lift on hover" treatment that
    made static data panels feel like marketing cards.
  - Heading changed from "Admin Operations Dashboard" to "Admin Operations
    Console" with a one-line subtitle — purely a copy/positioning tweak.
- `admin_dashboard/templates/admin_dashboard/customer_detail.html` and
  `templates/loans/admin_loan_detail.html` were **not** modified — they
  already use `.vb-card`/`.vb-data-card` and a self-contained, already
  well-designed style block, so they inherit the token refinements for
  free with zero risk of touching their logic.

### Auth pages
- `login.html`'s side panel (`.vb-auth-side`) now uses the same dark
  radial-gradient treatment as the landing-page hero and sidebar, instead
  of a flat purple gradient — ties the whole "logged-out" experience
  together visually.
- `admin_login.html` and `register.html` (`.vb-reg-card`) now pull their
  card shadow/radius from the shared token set instead of hard-coded
  pixel values, so a future token change propagates everywhere.
- `admin_register.html` needed no changes — it already used `.vb-data-card`.
- Register's 3-step wizard (progress stepper, demo autofill, inline
  validation) was left functionally and structurally as-is; it was already
  solid, this was a shadow/radius consistency pass only.

## 7. Files in this patch (cumulative, all 3 rounds)

| File                                                              | Type          |
|--------------------------------------------------------------------|---------------|
| `templates/base.html`                                               | FULL REPLACE  |
| `templates/landing.html`                                            | FULL REPLACE  |
| `static/css/style.css`                                              | FULL REPLACE  |
| `templates/upi/dashboard.html`                                      | FULL REPLACE  |
| `templates/upi/send_money.html`                                     | FULL REPLACE  |
| `templates/upi/transactions.html`                                   | FULL REPLACE  |
| `templates/upi/budgets.html`                                        | NEW FILE      |
| `templates/accounts/profile.html`                                   | FULL REPLACE  |
| `templates/accounts/set_pin.html`                                   | FULL REPLACE  |
| `templates/accounts/login.html`                                     | unchanged (benefits from CSS token update) |
| `templates/accounts/admin_login.html`                               | FULL REPLACE  |
| `templates/accounts/register.html`                                  | FULL REPLACE  |
| `templates/loans/my_loans.html`                                     | FULL REPLACE  |
| `templates/loans/apply.html`                                        | FULL REPLACE  |
| `templates/loans/loan_detail.html`                                  | FULL REPLACE  |
| `admin_dashboard/templates/admin_dashboard/dashboard.html`          | FULL REPLACE  |
| `upi/models.py`                                                     | FULL REPLACE  |
| `upi/admin.py`                                                      | FULL REPLACE  |
| `upi/views.py`                                                      | FULL REPLACE  |
| `upi/urls.py`                                                       | FULL REPLACE  |
| `upi/migrations/0012_transaction_category_budget.py`                | NEW FILE      |

Not modified anywhere in this patch: `admin_dashboard/templates/admin_dashboard/customer_detail.html`,
`templates/loans/admin_loan_detail.html`, `templates/accounts/admin_register.html`,
`templates/accounts/login.html` — they either already used shared classes
(and inherit the token updates automatically) or were already well-built
and out of scope for a visual pass.

## 9. Round 4 — genuinely finishing the "not modified" list

Last round's README said `customer_detail.html`, `admin_loan_detail.html`,
and `admin_register.html` didn't need changes because they already used
shared classes. That's true for visual consistency, but on a second look
there was real, missing functionality worth adding — so this round adds it
instead of just re-confirming they were fine.

### Notification bell (customer topbar) — new
- The notification system already existed server-side (admin can send
  presets/custom notifications, `Notification` model, `fetch_notifications`
  endpoint) but had **no UI surface** in the new sidebar shell. Customers
  had no way to see notifications outside the dashboard's own inline list.
- Added a bell icon + unread dot in the app-shell topbar, present on every
  customer page. Clicking it opens a dropdown that fetches and marks
  notifications as read (reusing the existing endpoint); a lightweight new
  read-only endpoint (`upi:notifications_unread_count`) powers the dot
  without marking anything read just from loading a page.
- **Fixed a real, pre-existing bug** while wiring this up:
  `fetch_notifications` called `.filter(is_read=False)` on a queryset that
  had already been sliced (`[:15]`), which raises
  `TypeError: Cannot filter a query once a slice has been taken.` — this
  was broken before my changes; it's fixed now (count computed before the
  slice).

### Customer Detail (admin view) — new stats
- Added a 4-box quick-glance stat strip above the existing KYC/accounts
  layout: total balance, total transaction count, success/failed split,
  and active loan count. Backed by real aggregation in
  `admin_dashboard/views.py::customer_detail_view` (not hardcoded).
- Everything else on this page was left as-is — it was already a
  well-built "customer 360" view; this adds to it rather than replacing it.

### Admin Loan Detail — cross-navigation
- Added a "View Customer Profile" link next to the existing back button,
  so an admin reviewing a loan can jump straight to that customer's full
  detail page instead of navigating back through the dashboard tabs.

### Admin Register / Login / Register — token consistency only
- No functional changes this round; these already got shadow/radius token
  updates in Round 3 and didn't need further work.

## 10. Files in this patch (Round 4 additions/changes)

| File                                                                | Type          |
|------------------------------------------------------------------------|---------------|
| `templates/base.html`                                                   | FULL REPLACE  |
| `static/css/style.css`                                                  | FULL REPLACE  |
| `upi/views.py`                                                          | FULL REPLACE  |
| `upi/urls.py`                                                           | FULL REPLACE  |
| `admin_dashboard/views.py`                                              | FULL REPLACE  |
| `admin_dashboard/templates/admin_dashboard/customer_detail.html`       | FULL REPLACE  |
| `templates/loans/admin_loan_detail.html`                                | FULL REPLACE  |

(All files from Rounds 1–3 are still included below for a complete,
one-shot patch — see sections above for what each one does.)

## 11. Tested (Round 4 additions)

- Fresh `migrate` + `check` — clean.
- Seeded a user with two `Notification` rows, then hit
  `/upi/notifications/unread-count/` and `/upi/notifications/` via the test
  client — both return correct JSON (`{"unread_count": 0}` after read,
  proper notification list before).
- This surfaced and confirmed the fix for the pre-existing slice/filter bug
  in `fetch_notifications` — reproduced the `TypeError` first, then
  verified it's gone after the fix.
- Rendered `/admin-dashboard/customer/<id>/` and confirmed the new stat
  strip (`cd-stat-strip`, "Total balance") is present with no leaked
  template tags.
- Rendered `/loans/<application_id>/admin/` and confirmed the new "View
  Customer Profile" link is present, no leaked template tags.
- Full role-based regression re-run (anonymous / customer / staff) across
  every previously-tested URL plus the two new notification endpoints —
  all 200.

