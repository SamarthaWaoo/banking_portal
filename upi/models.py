import random
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

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
    ('FLAGGED', 'Flagged'),
)

SPEND_CATEGORIES = (
    ('FOOD', 'Food & Dining'),
    ('SHOPPING', 'Shopping'),
    ('BILLS', 'Bills & Utilities'),
    ('ENTERTAINMENT', 'Entertainment'),
    ('HEALTH', 'Health & Wellness'),
    ('TRAVEL', 'Travel & Transport'),
    ('TRANSFER', 'Transfer'),
    ('OTHER', 'Other'),
)

# Icon + accent colour used consistently across dashboard, charts and budgets
CATEGORY_META = {
    'FOOD':          {'icon': 'bi-cup-hot',          'color': '#F59E0B'},
    'SHOPPING':      {'icon': 'bi-bag',              'color': '#EC4899'},
    'BILLS':         {'icon': 'bi-receipt',          'color': '#3B82F6'},
    'ENTERTAINMENT': {'icon': 'bi-film',              'color': '#8B5CF6'},
    'HEALTH':        {'icon': 'bi-heart-pulse',       'color': '#10B981'},
    'TRAVEL':        {'icon': 'bi-airplane',          'color': '#06B6D4'},
    'TRANSFER':      {'icon': 'bi-arrow-left-right',  'color': '#7C3AED'},
    'OTHER':         {'icon': 'bi-three-dots',        'color': '#6B7280'},
}


class BankAccount(models.Model):
    """
    The one and only bank account record per user.
    Security/lockout fields live on CustomUser — not here.
    This model is purely a financial ledger.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounts'
    )
    account_number = models.CharField(max_length=16, unique=True, blank=True)
    ifsc_code = models.CharField(max_length=11, default='VRTX0001234')
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES, default='SAVINGS')
    upi_id = models.CharField(max_length=50, unique=True, blank=True)
    balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    blocked_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0.00')
    )
    daily_transfer_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('100000.00')
    )
    is_active = models.BooleanField(default=True)
    is_rejected = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)   # admin must approve before account is usable
    requested_balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Initial deposit amount requested by customer at registration'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Generate account number if missing
        if not self.account_number:
            self.account_number = self._generate_account_number()
        # Generate UPI ID if missing
        if not self.upi_id:
            self.upi_id = f"{self.user.username}{random.randint(100, 999)}@spendsmartbank"
        # Balance stays 0 until admin approves the account.
        super().save(*args, **kwargs)

    def _generate_account_number(self):
        while True:
            num = "".join([str(random.randint(0, 9)) for _ in range(14)])
            if not BankAccount.objects.filter(account_number=num).exists():
                return num

    def amount_transferred_today(self):
        now = timezone.localtime(timezone.now())
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timezone.timedelta(days=1)
        total = self.sent_transactions.filter(
            timestamp__gte=day_start, timestamp__lt=day_end, status='SUCCESS'
        ).aggregate(models.Sum('amount'))['amount__sum']
        return total or Decimal('0.00')

    def masked_number(self):
        """Returns XXXX-XXXX-XXXX-1234 style for display."""
        n = self.account_number
        if len(n) <= 4:
            return n
        return ('X' * (len(n) - 4)) + n[-4:]

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
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))]
    )
    transaction_type = models.CharField(
        max_length=10, choices=TRANSACTION_TYPES, default='SEND'
    )
    status = models.CharField(
        max_length=10, choices=TRANSACTION_STATUS, default='PENDING'
    )
    note = models.CharField(max_length=140, blank=True)
    category = models.CharField(
        max_length=20, choices=SPEND_CATEGORIES, default='OTHER', blank=True
    )
    failure_reason = models.CharField(max_length=200, blank=True)
    sender_balance_after = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    receiver_balance_after = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    is_flagged = models.BooleanField(default=False)
    resolved = models.BooleanField(default=False)
    resolution_note = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference_id:
            self.reference_id = "TXN" + uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.reference_id} - {self.amount} - {self.status}"

    def category_icon(self):
        return CATEGORY_META.get(self.category, CATEGORY_META['OTHER'])['icon']

    def category_color(self):
        return CATEGORY_META.get(self.category, CATEGORY_META['OTHER'])['color']


class RecentContact(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recent_contacts'
    )
    contact_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE
    )
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_used']
        unique_together = ('user', 'contact_account')

    def __str__(self):
        return f"{self.user.username} → {self.contact_account.upi_id}"


class Beneficiary(models.Model):
    """Saved/favourite recipients for quick send."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='beneficiaries'
    )
    account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE
    )
    nickname = models.CharField(max_length=40, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nickname', 'added_at']
        unique_together = ('user', 'account')

    def __str__(self):
        return f"{self.user.username} → {self.account.upi_id} ({self.nickname})"


class Budget(models.Model):
    """
    A per-category monthly spending goal set by the customer.
    Progress is always computed live against SUCCESS 'SEND' transactions
    for the current calendar month — nothing is pre-aggregated/cached,
    so it can never drift out of sync with the ledger.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='budgets'
    )
    category = models.CharField(max_length=20, choices=SPEND_CATEGORIES)
    monthly_limit = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'category')
        ordering = ['category']

    def __str__(self):
        return f"{self.user.username} · {self.get_category_display()} · ₹{self.monthly_limit}/mo"

    def icon(self):
        return CATEGORY_META.get(self.category, CATEGORY_META['OTHER'])['icon']

    def color(self):
        return CATEGORY_META.get(self.category, CATEGORY_META['OTHER'])['color']

    def spent_this_month(self):
        # Use a plain datetime RANGE instead of timestamp__year=/timestamp__month=.
        # Those lookups make MySQL run CONVERT_TZ() to translate UTC -> TIME_ZONE
        # before extracting year/month — if MySQL's timezone tables aren't loaded
        # (mysql_tzinfo_to_sql), CONVERT_TZ silently returns NULL and the filter
        # matches nothing, even for transactions that are clearly there.
        # A range filter compares datetimes directly and never needs CONVERT_TZ.
        now = timezone.localtime(timezone.now())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month_start.month == 12:
            next_month_start = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month_start = month_start.replace(month=month_start.month + 1)

        total = Transaction.objects.filter(
            sender_account__user=self.user,
            category=self.category,
            status='SUCCESS',
            timestamp__gte=month_start,
            timestamp__lt=next_month_start,
        ).aggregate(models.Sum('amount'))['amount__sum']
        return total or Decimal('0.00')

    def percent_used(self):
        if not self.monthly_limit:
            return 0
        pct = (self.spent_this_month() / self.monthly_limit) * 100
        return int(min(pct, 999))

    def remaining(self):
        return self.monthly_limit - self.spent_this_month()

    def overage(self):
        rem = self.remaining()
        return -rem if rem < 0 else Decimal('0.00')

    def status_level(self):
        """'ok' | 'warn' | 'over' — drives the progress-bar colour."""
        pct = self.percent_used()
        if pct >= 100:
            return 'over'
        if pct >= 80:
            return 'warn'
        return 'ok'