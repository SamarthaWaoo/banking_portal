from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('upi', '0007_beneficiary'),
    ]

    operations = [
        migrations.AddField(
            model_name='bankaccount',
            name='is_approved',
            field=models.BooleanField(default=False, help_text='Admin must approve before account is usable'),
        ),
        migrations.AddField(
            model_name='bankaccount',
            name='requested_balance',
            field=models.DecimalField(
                max_digits=14, decimal_places=2, default=0,
                help_text='Initial deposit amount requested by customer at registration'
            ),
        ),
    ]
