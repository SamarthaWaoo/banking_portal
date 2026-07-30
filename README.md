# SpendSmart Bank — Digital Banking Suite

A full-stack simulated digital banking platform built with **Django, SQLite, and Bootstrap 5**, combining a **UPI-style payments module** and a **loan eligibility & management module** under one bank-themed website.

Built as a portfolio project to demonstrate backend, database, and business-logic skills relevant to fintech/banking software roles.

> ⚠️ **This is a simulation.** No real money, banks, or KYC providers are involved. PAN/Aadhaar fields are validated by format (regex) only.

---

## Features

### UPI Payments Module
- Auto-generated bank account + UPI ID on signup
- Send/receive money between accounts, protected by a 4-digit transaction PIN
- **Atomic, race-condition-safe transfers** using `transaction.atomic()` + `select_for_update()`
- Daily transfer limit enforcement
- Full transaction history with status filters (Success/Failed)
- Every failed attempt is logged too — a real audit trail, not just successes
- Downloadable PDF account statement (via `reportlab`)

### Loan Eligibility Module
- Application form: salary, expenses, existing EMI, credit score, loan amount, tenure
- EMI calculated with the standard reducing-balance formula
- Debt-to-Income (DTI) ratio computation
- Transparent, rule-based approval engine (not a black box — see below)
- Full month-by-month amortization schedule for approved loans

### General
- Bank-themed responsive UI (navy + gold palette) built with Bootstrap 5
- Custom user model with simulated KYC fields
- Django Admin customized for "bank operations" use
- Unit tests covering EMI/DTI math and transfer edge cases

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6 |
| Database | SQLite (dev) |
| Frontend | Django Templates + Bootstrap 5 + Bootstrap Icons |
| PDF generation | ReportLab |
| Static files | WhiteNoise |
| Deployment | Render (free tier) + Gunicorn |

---

## Local Setup

```bash
git clone <your-repo-url>
cd banksuite

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`.

---

## Project Structure

```
banksuite/
├── accounts/       # Custom user model, registration, login, PIN, profile
├── upi/            # Bank accounts, transactions, send money, PDF statement
├── loans/          # Loan applications, EMI/DTI engine, amortization
├── templates/       # Bank-themed HTML (base, landing, accounts/, upi/, loans/)
├── static/css/      # Custom theme (navy + gold banking palette)
├── banksuite/       # Project settings, urls
├── build.sh          # Render build script
├── Procfile           # Gunicorn start command
└── requirements.txt
```

## Running Tests

```bash
python manage.py test
```

Covers: EMI calculation accuracy, DTI computation, approval/rejection logic, amortization schedule correctness, atomic money transfer, insufficient-balance handling, wrong-PIN blocking, and daily-limit enforcement.
