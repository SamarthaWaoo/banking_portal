from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_customuser_avatar_customuser_is_admin_account'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='failed_pin_attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='customuser',
            name='pin_locked_until',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # The old Account stub table was created in 0002 but is unused.
        # We delete it cleanly here so it doesn't pollute the DB.
        migrations.DeleteModel(
            name='Account',
        ),
    ]
