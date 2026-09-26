from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('preset', models.CharField(
                    choices=[
                        ('welcome', 'Welcome to SpendSmart Bank!'),
                        ('approved', 'Account Approved'),
                        ('freeze_warning', 'Account Freeze Warning'),
                        ('loan_approved', 'Loan Application Approved'),
                        ('loan_rejected', 'Loan Application Rejected'),
                        ('festival_offer', 'Festival Offer'),
                        ('rate_update', 'Interest Rate Update'),
                        ('referral', 'Referral Programme'),
                        ('custom', 'Custom Message'),
                    ],
                    default='custom', max_length=30
                )),
                ('title', models.CharField(max_length=120)),
                ('body', models.TextField()),
                ('icon', models.CharField(default='bi-bell', help_text='Bootstrap icon class', max_length=40)),
                ('is_read', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to=settings.AUTH_USER_MODEL,
                    help_text='Leave blank to broadcast to ALL customers.'
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
