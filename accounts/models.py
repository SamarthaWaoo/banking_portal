import random
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User
from django.utils import timezone

class Account(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE) # <-- Fixed!
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    pin = models.CharField(max_length=128) # Hashed PIN recommended
    failed_pin_attempts = models.IntegerField(default=0)
    lockout_until = models.DateTimeField(null=True, blank=True)

    def is_locked(self):
        if self.lockout_until and timezone.now() < self.lockout_until:
            return True
        return False

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
    Extended user model for BankSuite.
    Note: PAN/Aadhaar here are FORMAT-VALIDATED ONLY (regex), not verified
    against any government API. This is a simulated KYC flow for demo purposes.
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
    is_kyc_verified = models.BooleanField(default=True)  # auto-true in simulation
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.customer_id = self._generate_customer_id()
        super().save(*args, **kwargs)

    def _generate_customer_id(self):
        while True:
            cid = "VB" + "".join([str(random.randint(0, 9)) for _ in range(8)])
            if not CustomUser.objects.filter(customer_id=cid).exists():
                return cid

    def set_transaction_pin(self, raw_pin):
        self.pin_hash = make_password(raw_pin)

    def check_transaction_pin(self, raw_pin):
        if not self.pin_hash:
            return False
        return check_password(raw_pin, self.pin_hash)

    def __str__(self):
        return f"{self.username} ({self.customer_id})"
