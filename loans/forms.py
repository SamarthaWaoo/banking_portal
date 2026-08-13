from django import forms
from .models import LoanApplication


class LoanApplicationForm(forms.ModelForm):
    loan_type = forms.ChoiceField(
        choices=[('', '— Select Loan Type —')] + [
            ('PERSONAL', 'Personal Loan'),
            ('HOME', 'Home Loan'),
            ('CAR', 'Car Loan'),
            ('EDUCATION', 'Education Loan'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
    )

    class Meta:
        model = LoanApplication
        fields = [
            'loan_type', 'monthly_salary', 'monthly_expenses',
            'existing_emi', 'credit_score', 'loan_amount', 'tenure_months',
            'interest_rate',
        ]
        widgets = {
            'loan_type': forms.Select(attrs={'class': 'form-select'}),
            'monthly_salary': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 60000', 'inputmode': 'decimal', 'autocomplete': 'off'}),
            'monthly_expenses': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 20000', 'inputmode': 'decimal', 'autocomplete': 'off'}),
            'existing_emi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0', 'inputmode': 'decimal', 'autocomplete': 'off'}),
            'credit_score': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '300-900'}),
            'loan_amount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 500000', 'inputmode': 'decimal', 'autocomplete': 'off'}),
            'tenure_months': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 36', 'inputmode': 'numeric', 'autocomplete': 'off'}),
            'interest_rate': forms.NumberInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. 11.5 (leave blank for default)',
                'step': '0.1', 'min': '1', 'max': '36', 'autocomplete': 'off',
            }),
        }

    def clean_credit_score(self):
        score = self.cleaned_data['credit_score']
        if score < 300 or score > 900:
            raise forms.ValidationError("Credit score must be between 300 and 900.")
        return score

    def clean_loan_type(self):
        loan_type = self.cleaned_data.get('loan_type', '')
        if not loan_type:
            raise forms.ValidationError("Please select a loan type.")
        return loan_type
