"""
Data migration: auto-approve every BankAccount that existed before the
is_approved field was introduced (requested_balance=0, balance already set).
These are real live accounts that should never have been pending.
"""
from django.db import migrations


def approve_legacy_accounts(apps, schema_editor):
    BankAccount = apps.get_model('upi', 'BankAccount')
    # Old accounts: is_approved=False AND requested_balance=0
    # They already have a real balance set (were created before the approval flow).
    updated = BankAccount.objects.filter(
        is_approved=False,
        requested_balance=0,
    ).update(is_approved=True, is_active=True)
    print(f"  Auto-approved {updated} legacy account(s).")


class Migration(migrations.Migration):

    dependencies = [
        ('upi', '0009_alter_bankaccount_is_approved'),
    ]

    operations = [
        migrations.RunPython(approve_legacy_accounts, migrations.RunPython.noop),
    ]
