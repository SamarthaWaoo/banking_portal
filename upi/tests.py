from decimal import Decimal
from django.test import TestCase, Client
from accounts.models import CustomUser
from .models import BankAccount, Transaction


class UpiTransferTests(TestCase):
    def setUp(self):
        self.sender = CustomUser.objects.create_user(
            username='sender', password='pass1234',
            pan_number='ABCDE1234F', aadhaar_number='111122223333',
            phone_number='9876543210',
        )
        self.sender.set_transaction_pin('1234')
        self.sender.save()

        self.receiver = CustomUser.objects.create_user(
            username='receiver', password='pass1234',
            pan_number='PQRSX5678K', aadhaar_number='444455556666',
            phone_number='9123456780',
        )

        self.sender_acc = BankAccount.objects.create(user=self.sender, balance=Decimal('10000.00'))
        self.receiver_acc = BankAccount.objects.create(user=self.receiver, balance=Decimal('5000.00'))

        self.client = Client()
        self.client.login(username='sender', password='pass1234')

    def test_successful_transfer_updates_balances(self):
        response = self.client.post('/upi/send/', {
            'sender_account': self.sender_acc.id,
            'receiver_upi_id': self.receiver_acc.upi_id,
            'amount': '1000',
            'note': 'test',
            'pin': '1234',
        }, follow=True)
        self.sender_acc.refresh_from_db()
        self.receiver_acc.refresh_from_db()
        self.assertEqual(self.sender_acc.balance, Decimal('9000.00'))
        self.assertEqual(self.receiver_acc.balance, Decimal('6000.00'))
        txn = Transaction.objects.filter(status='SUCCESS').first()
        self.assertIsNotNone(txn)

    def test_insufficient_balance_fails_and_logs_failure(self):
        response = self.client.post('/upi/send/', {
            'sender_account': self.sender_acc.id,
            'receiver_upi_id': self.receiver_acc.upi_id,
            'amount': '999999',
            'note': 'too much',
            'pin': '1234',
        }, follow=True)
        self.sender_acc.refresh_from_db()
        self.assertEqual(self.sender_acc.balance, Decimal('10000.00'))
        failed_txn = Transaction.objects.filter(status='FAILED').first()
        self.assertIsNotNone(failed_txn)
        self.assertIn('Insufficient', failed_txn.failure_reason)

    def test_wrong_pin_blocks_transfer(self):
        self.client.post('/upi/send/', {
            'sender_account': self.sender_acc.id,
            'receiver_upi_id': self.receiver_acc.upi_id,
            'amount': '500',
            'note': 'wrong pin',
            'pin': '0000',
        }, follow=True)
        self.sender_acc.refresh_from_db()
        self.assertEqual(self.sender_acc.balance, Decimal('10000.00'))

    def test_daily_limit_enforced(self):
        self.sender_acc.daily_transfer_limit = Decimal('100.00')
        self.sender_acc.save()
        self.client.post('/upi/send/', {
            'sender_account': self.sender_acc.id,
            'receiver_upi_id': self.receiver_acc.upi_id,
            'amount': '500',
            'note': 'exceeds limit',
            'pin': '1234',
        }, follow=True)
        self.sender_acc.refresh_from_db()
        self.assertEqual(self.sender_acc.balance, Decimal('10000.00'))
