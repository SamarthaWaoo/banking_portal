from django import forms
from .models import LoanApplication


class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        fields = [
            'loan_type', 'monthly_salary', 'monthly_expenses',
            'existing_emi', 'credit_score', 'loan_amount', 'tenure_months',
        ]
        widgets = {
            'loan_type': forms.Select(attrs={'class': 'form-select'}),
            'monthly_salary': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 60000'}),
            'monthly_expenses': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 20000'}),
            'existing_emi': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0'}),
            'credit_score': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '300-900'}),
            'loan_amount': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 500000'}),
            'tenure_months': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 36'}),
        }

    def clean_credit_score(self):
        score = self.cleaned_data['credit_score']
        if score < 300 or score > 900:
            raise forms.ValidationError("Credit score must be between 300 and 900.")
        return score
