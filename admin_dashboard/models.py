from django.db import models
from django.conf import settings


class Notification(models.Model):
    """
    Admin-to-customer direct message / notification.
    Appears in the customer's dashboard feed.
    """
    PRESET_CHOICES = [
        ('welcome',        'Welcome to SpendSmart Bank!'),
        ('approved',       'Account Approved'),
        ('freeze_warning', 'Account Freeze Warning'),
        ('loan_approved',  'Loan Application Approved'),
        ('loan_rejected',  'Loan Application Rejected'),
        ('festival_offer', 'Festival Offer'),
        ('rate_update',    'Interest Rate Update'),
        ('referral',       'Referral Programme'),
        ('custom',         'Custom Message'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', null=True, blank=True,
        help_text='Leave blank to broadcast to ALL customers.'
    )
    preset   = models.CharField(max_length=30, choices=PRESET_CHOICES, default='custom')
    title    = models.CharField(max_length=120)
    body     = models.TextField()
    icon     = models.CharField(max_length=40, default='bi-bell',
                                help_text='Bootstrap icon class, e.g. bi-gift')
    is_read  = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        target = self.recipient.username if self.recipient else 'ALL'
        return f"[{target}] {self.title}"
