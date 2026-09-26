# Generated for the Budgets & Spending Insights feature

import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('upi', '0011_bankaccount_is_rejected'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='category',
            field=models.CharField(
                blank=True,
                choices=[
                    ('FOOD', 'Food & Dining'),
                    ('SHOPPING', 'Shopping'),
                    ('BILLS', 'Bills & Utilities'),
                    ('ENTERTAINMENT', 'Entertainment'),
                    ('HEALTH', 'Health & Wellness'),
                    ('TRAVEL', 'Travel & Transport'),
                    ('TRANSFER', 'Transfer'),
                    ('OTHER', 'Other'),
                ],
                default='OTHER',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='Budget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(
                    choices=[
                        ('FOOD', 'Food & Dining'),
                        ('SHOPPING', 'Shopping'),
                        ('BILLS', 'Bills & Utilities'),
                        ('ENTERTAINMENT', 'Entertainment'),
                        ('HEALTH', 'Health & Wellness'),
                        ('TRAVEL', 'Travel & Transport'),
                        ('TRANSFER', 'Transfer'),
                        ('OTHER', 'Other'),
                    ],
                    max_length=20,
                )),
                ('monthly_limit', models.DecimalField(
                    decimal_places=2, max_digits=12,
                    validators=[django.core.validators.MinValueValidator(Decimal('1.00'))]
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='budgets', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['category'],
                'unique_together': {('user', 'category')},
            },
        ),
    ]
