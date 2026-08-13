from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('upi', '0006_alter_bankaccount_balance_delete_beneficiary'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Beneficiary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nickname', models.CharField(blank=True, max_length=40)),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='upi.bankaccount',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='beneficiaries',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['nickname', 'added_at'],
                'unique_together': {('user', 'account')},
            },
        ),
    ]
