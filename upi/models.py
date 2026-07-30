import random
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator


ACCOUNT_TYPES = (
    ('SAVINGS', 'Savings Account'),
    ('CURRENT', 'Current Account'),
)

TRANSACTION_TYPES = (
    ('SEND', 'Money Sent'),
    ('RECEIVE', 'Money Received'),
    ('SELF', 'Self Transfer'),
)

TRANSACTION_STATUS = (
    ('SUCCESS', 'Success'),
    ('FAILED', 'Failed'),
    ('PENDING', 'Pending'),
)


class BankAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounts')
    account_number = models.CharField(max_length=16, unique=True, blank=True)
    ifsc_code = models.CharField(max_length=11, default='VRTX0001234')
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES, default='SAVINGS')
    upi_id = models.CharField(max_length=50, unique=True, blank=True)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('10000.00'),
                                   validators=[MinValueValidator(Decimal('0.00'))])
    daily_transfer_limit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100000.00'))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self._generate_account_number()
        if not self.upi_id:
            self.upi_id = f"{self.user.username}{random.randint(100,999)}@spendsmartbank"
        super().save(*args, **kwargs)

    def _generate_account_number(self):
        while True:
            num = "".join([str(random.randint(0, 9)) for _ in range(14)])
            if not BankAccount.objects.filter(account_number=num).exists():
                return num

    def amount_transferred_today(self):
        from django.utils import timezone
        today = timezone.now().date()
        total = self.sent_transactions.filter(
            timestamp__date=today, status='SUCCESS'
        ).aggregate(models.Sum('amount'))['amount__sum']
        return total or Decimal('0.00')

    def __str__(self):
        return f"{self.account_number} ({self.user.username})"


class Transaction(models.Model):
    reference_id = models.CharField(max_length=20, unique=True, blank=True)
    sender_account = models.ForeignKey(
        BankAccount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sent_transactions'
    )
    receiver_account = models.ForeignKey(
        BankAccount, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='received_transactions'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('1.00'))])
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES, default='SEND')
    status = models.CharField(max_length=10, choices=TRANSACTION_STATUS, default='PENDING')
    note = models.CharField(max_length=140, blank=True)
    failure_reason = models.CharField(max_length=140, blank=True)
    sender_balance_after = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    receiver_balance_after = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.reference_id:
            self.reference_id = "TXN" + uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.reference_id} - {self.amount} - {self.status}"
