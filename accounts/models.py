import random
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from django.conf import settings

pan_validator = RegexValidator(
    regex=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$',
    message="Enter a valid PAN number (format: ABCDE1234F)"
)

aadhaar_validator = RegexValidator(
    regex=r'^\d{12}$',
    message="Aadhaar number must be exactly 12 digits"
)

phone_validator = RegexValidator(
    regex=r'^[6-9]\d{9}$',
    message="Enter a valid 10-digit mobile number"
)


class CustomUser(AbstractUser):
    """
    Single authoritative user model for BankSuite.
    All lockout / PIN security lives here on the user,
    NOT on the BankAccount — which is purely a financial record.
    """
    pan_number = models.CharField(
        max_length=10, unique=True, validators=[pan_validator],
        help_text="Format: ABCDE1234F"
    )
    aadhaar_number = models.CharField(
        max_length=12, unique=True, validators=[aadhaar_validator]
    )
    phone_number = models.CharField(
        max_length=10, validators=[phone_validator]
    )
    date_of_birth = models.DateField(null=True, blank=True)
    pin_hash = models.CharField(max_length=128, blank=True, null=True)
    customer_id = models.CharField(max_length=12, unique=True, blank=True)
    is_kyc_verified = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    avatar = models.CharField(max_length=255, blank=True, null=True)
    is_admin = models.BooleanField(default=False)

    # --- PIN lockout (lives on the user, applied at send-money time) ---
    failed_pin_attempts = models.PositiveSmallIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)

    MAX_PIN_ATTEMPTS = 3
    PIN_LOCKOUT_MINUTES = 5

    def is_pin_locked(self):
        return bool(self.pin_locked_until and timezone.now() < self.pin_locked_until)

    def pin_lock_remaining_seconds(self):
        if not self.is_pin_locked():
            return 0
        return max(0, int((self.pin_locked_until - timezone.now()).total_seconds()))

    def register_failed_pin(self):
        self.failed_pin_attempts += 1
        if self.failed_pin_attempts >= self.MAX_PIN_ATTEMPTS:
            self.pin_locked_until = timezone.now() + timezone.timedelta(minutes=self.PIN_LOCKOUT_MINUTES)
        self.save(update_fields=['failed_pin_attempts', 'pin_locked_until'])

    def reset_pin_attempts(self):
        if self.failed_pin_attempts or self.pin_locked_until:
            self.failed_pin_attempts = 0
            self.pin_locked_until = None
            self.save(update_fields=['failed_pin_attempts', 'pin_locked_until'])

    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.customer_id = self._generate_customer_id()
        if not self.avatar:
            self.avatar = self._assign_random_avatar()
        super().save(*args, **kwargs)

    def _generate_customer_id(self):
        while True:
            cid = "VB" + "".join([str(random.randint(0, 9)) for _ in range(8)])
            if not CustomUser.objects.filter(customer_id=cid).exists():
                return cid

    def _assign_random_avatar(self):
        styles = ["bottts", "avataaars", "micah", "identicon"]
        style = random.choice(styles)
        return f"https://api.dicebear.com/6.x/{style}/png?seed={self.username}"

    def set_transaction_pin(self, raw_pin):
        self.pin_hash = make_password(raw_pin)

    def check_transaction_pin(self, raw_pin):
        if not self.pin_hash:
            return False
        return check_password(raw_pin, self.pin_hash)

    def __str__(self):
        return f"{self.username} ({self.customer_id})"
