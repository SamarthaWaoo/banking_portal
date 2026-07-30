from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from upi.models import BankAccount  # Ensure this matches your model import

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds multiple demo user profiles for repository evaluators'

    def handle(self, *args, **kwargs):
        demo_accounts = [
            {
                "username": "demouser1",
                "email": "demo1@spendsmart.com",
                "password": "DemoPassword123!",
                "balance": 25000.00
            },
            {
                "username": "demouser2",
                "email": "demo2@spendsmart.com",
                "password": "DemoPassword123!",
                "balance": 50000.00
            },
            {
                "username": "demouser3",
                "email": "demo3@spendsmart.com",
                "password": "DemoPassword123!",
                "balance": 100000.00
            }
        ]

        for data in demo_accounts:
            if User.objects.filter(email=data["email"]).exists():
                self.stdout.write(self.style.WARNING(f"Demo user {data['email']} already exists!"))
                continue

            # Create demo user safely with hashed password
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password=data["password"]
            )
            
            # Provision initial mock bank profile data
            BankAccount.objects.get_or_create(
                user=user,
                defaults={
                    'balance': data["balance"],
                    'upi_id': f"{data['username']}@spendsmart"
                }
            )

            self.stdout.write(self.style.SUCCESS(f"Successfully created demo user: {data['email']} / {data['password']}"))