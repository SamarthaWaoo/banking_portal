import random
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator

LOAN_TYPES = (
    ('PERSONAL', 'Personal Loan'),
    ('HOME', 'Home Loan'),
    ('CAR', 'Car Loan'),
    ('EDUCATION', 'Education Loan'),
)

STATUS_CHOICES = (
    ('PENDING', 'Under Review'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
)

# Simple base interest rates by loan type (annual %)
BASE_INTEREST_RATES = {
    'PERSONAL': Decimal('12.5'),
    'HOME': Decimal('8.5'),
    'CAR': Decimal('9.5'),
    'EDUCATION': Decimal('10.0'),
}


class LoanApplication(models.Model):
    application_id = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loan_applications')
    loan_type = models.CharField(max_length=12, choices=LOAN_TYPES, default='PERSONAL')
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    monthly_expenses = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0'))])
    existing_emi = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    credit_score = models.IntegerField(validators=[MinValueValidator(300)])
    loan_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('1000'))])
    tenure_months = models.IntegerField(validators=[MinValueValidator(3)])
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    dti_ratio = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    emi_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    decision_reason = models.CharField(max_length=255, blank=True)

    applied_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-applied_at']

    def save(self, *args, **kwargs):
        if not self.application_id:
            self.application_id = "LN" + uuid.uuid4().hex[:10].upper()
        if not self.interest_rate:
            self.interest_rate = BASE_INTEREST_RATES.get(self.loan_type, Decimal('11.0'))
        super().save(*args, **kwargs)

    def calculate_emi(self):
        """Reducing balance EMI formula: EMI = P x r x (1+r)^n / ((1+r)^n - 1)"""
        p = float(self.loan_amount)
        r = float(self.interest_rate) / 12 / 100
        n = self.tenure_months
        if r == 0:
            return round(p / n, 2)
        emi = p * r * (1 + r) ** n / ((1 + r) ** n - 1)
        return round(emi, 2)

    def calculate_dti(self):
        """Debt-to-Income ratio including proposed EMI, as a percentage."""
        income = float(self.monthly_salary)
        if income == 0:
            return 100.0
        total_obligations = float(self.monthly_expenses) + float(self.existing_emi) + self.calculate_emi()
        return round((total_obligations / income) * 100, 2)

    def evaluate(self):
        """
        Rule-based approval engine (deliberately simple & documented):
        - Credit score must be >= 650
        - DTI ratio (including new EMI) must be <= 45%
        - Requested EMI must not exceed 60% of (salary - expenses)
        """
        self.emi_amount = Decimal(str(self.calculate_emi()))
        self.dti_ratio = Decimal(str(self.calculate_dti()))

        reasons = []
        if self.credit_score < 650:
            reasons.append(f"Credit score {self.credit_score} is below the minimum requirement of 650")
        if self.dti_ratio > 45:
            reasons.append(f"Debt-to-income ratio {self.dti_ratio}% exceeds the 45% threshold")

        disposable = float(self.monthly_salary) - float(self.monthly_expenses)
        if disposable > 0 and float(self.emi_amount) > 0.6 * disposable:
            reasons.append("Proposed EMI exceeds 60% of disposable income")
        elif disposable <= 0:
            reasons.append("No disposable income after monthly expenses")

        if reasons:
            self.status = 'REJECTED'
            self.decision_reason = "; ".join(reasons)
        else:
            self.status = 'APPROVED'
            self.decision_reason = "Meets all eligibility criteria: credit score, DTI ratio, and EMI affordability"

        from django.utils import timezone
        self.decided_at = timezone.now()
        return self.status

    def amortization_schedule(self):
        """Returns list of dicts: month, principal_paid, interest_paid, balance"""
        schedule = []
        balance = float(self.loan_amount)
        r = float(self.interest_rate) / 12 / 100
        emi = float(self.emi_amount) if self.emi_amount else self.calculate_emi()
        for month in range(1, self.tenure_months + 1):
            interest = balance * r
            principal = emi - interest
            balance = max(balance - principal, 0)
            schedule.append({
                'month': month,
                'emi': round(emi, 2),
                'principal': round(principal, 2),
                'interest': round(interest, 2),
                'balance': round(balance, 2),
            })
        return schedule

    def __str__(self):
        return f"{self.application_id} - {self.user.username} - {self.status}"
