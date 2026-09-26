"""
Migration 0010: originally attempted to create a Notification model in the
upi app, but Notification lives in admin_dashboard (admin_dashboard/migrations/0001_initial.py).
This is now a no-op so the migration history stays intact without conflicts.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('upi', '0009_auto_approve_legacy_accounts'),
    ]

    operations = [
        # Notification model is owned by admin_dashboard — nothing to do here.
    ]
