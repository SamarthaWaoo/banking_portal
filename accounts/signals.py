from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, Account
import random

@receiver(post_save, sender=CustomUser)
def create_account_for_user(sender, instance, created, **kwargs):
    if created:
        starting_balance = random.randint(5000, 50000)
        Account.objects.create(
            user=instance,
            balance=starting_balance,
            blocked_balance=0,   # ensure blocked balance starts at 0
            pin="",              # empty until user sets transaction PIN
        )
