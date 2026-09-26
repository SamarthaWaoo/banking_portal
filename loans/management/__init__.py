"""
Sends EMI due-date reminder notifications at 10, 5, 3, and 1 day(s) before
each disbursed loan's next payment is due.

This is a one-shot command — Django itself has no built-in scheduler, so it
needs to be triggered once per day by something outside Django:

  - Linux/macOS: a cron entry, e.g.
        0 8 * * * cd /path/to/project && /path/to/venv/bin/python manage.py send_loan_reminders
  - Windows: Task Scheduler running
        python manage.py send_loan_reminders
    once a day (e.g. every morning).
  - Either way, running it more than once on the same day is safe — each
    loan's last_reminder_days field prevents the same threshold being sent
    twice for the same due month.

Usage: python manage.py send_loan_reminders
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from loans.models import LoanApplication

# Send a reminder exactly this many days before the due date.
REMINDER_THRESHOLDS = [10, 5, 3, 1]


class Command(BaseCommand):
    help = "Send EMI due-date reminder notifications before each loan's next due date."

    def handle(self, *args, **options):
        from admin_dashboard.models import Notification  # local import avoids app-loading order issues

        today = timezone.now().date()
        sent = 0

        loans = LoanApplication.objects.filter(status='DISBURSED').select_related('user')
        for loan in loans:
            due_date = loan.get_next_due_date()
            if not due_date:
                continue

            days_left = (due_date - today).days

            if days_left in REMINDER_THRESHOLDS and loan.last_reminder_days != days_left:
                day_word = "day" if days_left == 1 else "days"
                Notification.objects.create(
                    recipient=loan.user,
                    preset='custom',
                    title=f'EMI Due in {days_left} {day_word}',
                    body=(
                        f'Your {loan.get_loan_type_display()} EMI of ₹{loan.emi_amount} '
                        f'for loan {loan.application_id} is due on {due_date.strftime("%d %b %Y")}. '
                        'Pay it from your loan page to stay on schedule.'
                    ),
                    icon='bi-calendar-event',
                )
                loan.last_reminder_days = days_left
                loan.save(update_fields=['last_reminder_days'])
                sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} reminder notification(s).'))