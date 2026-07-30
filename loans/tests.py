from decimal import Decimal
from django.test import TestCase
from accounts.models import CustomUser
from .models import LoanApplication


class LoanCalculationTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser', password='pass1234',
            pan_number='ABCDE1234F', aadhaar_number='123456789012',
            phone_number='9876543210',
        )

    def test_emi_calculation_known_values(self):
        """EMI for 100000 at 12% p.a. for 12 months should be ~8884.88"""
        loan = LoanApplication(
            user=self.user, loan_type='PERSONAL', monthly_salary=Decimal('50000'),
            monthly_expenses=Decimal('10000'), existing_emi=Decimal('0'),
            credit_score=750, loan_amount=Decimal('100000'), tenure_months=12,
            interest_rate=Decimal('12.0'),
        )
        emi = loan.calculate_emi()
        self.assertAlmostEqual(emi, 8884.88, delta=1.0)

    def test_zero_interest_emi(self):
        loan = LoanApplication(
            user=self.user, loan_type='PERSONAL', monthly_salary=Decimal('50000'),
            monthly_expenses=Decimal('10000'), existing_emi=Decimal('0'),
            credit_score=750, loan_amount=Decimal('12000'), tenure_months=12,
            interest_rate=Decimal('0'),
        )
        self.assertEqual(loan.calculate_emi(), 1000.0)

    def test_approval_for_good_profile(self):
        loan = LoanApplication.objects.create(
            user=self.user, loan_type='PERSONAL', monthly_salary=Decimal('80000'),
            monthly_expenses=Decimal('15000'), existing_emi=Decimal('0'),
            credit_score=750, loan_amount=Decimal('300000'), tenure_months=36,
        )
        status = loan.evaluate()
        self.assertEqual(status, 'APPROVED')

    def test_rejection_for_low_credit_score(self):
        loan = LoanApplication.objects.create(
            user=self.user, loan_type='PERSONAL', monthly_salary=Decimal('80000'),
            monthly_expenses=Decimal('15000'), existing_emi=Decimal('0'),
            credit_score=500, loan_amount=Decimal('300000'), tenure_months=36,
        )
        status = loan.evaluate()
        self.assertEqual(status, 'REJECTED')
        self.assertIn('Credit score', loan.decision_reason)

    def test_rejection_for_high_dti(self):
        loan = LoanApplication.objects.create(
            user=self.user, loan_type='PERSONAL', monthly_salary=Decimal('25000'),
            monthly_expenses=Decimal('20000'), existing_emi=Decimal('5000'),
            credit_score=700, loan_amount=Decimal('500000'), tenure_months=24,
        )
        status = loan.evaluate()
        self.assertEqual(status, 'REJECTED')

    def test_amortization_schedule_length_and_final_balance(self):
        loan = LoanApplication.objects.create(
            user=self.user, loan_type='PERSONAL', monthly_salary=Decimal('80000'),
            monthly_expenses=Decimal('15000'), existing_emi=Decimal('0'),
            credit_score=750, loan_amount=Decimal('100000'), tenure_months=12,
        )
        loan.evaluate()
        loan.save()
        schedule = loan.amortization_schedule()
        self.assertEqual(len(schedule), 12)
        self.assertAlmostEqual(schedule[-1]['balance'], 0, delta=5.0)
