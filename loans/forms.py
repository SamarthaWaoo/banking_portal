from django import forms
from .models import LoanApplication


class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanApplication
        fields = [
            'loan_type', 'monthly_salary', 'monthly_expenses',
            'existing_emi', 'loan_amount', 'tenure_months',
            'interest_rate',
        ]
        widgets = {
            'loan_type': forms.Select(attrs={'class': 'form-select'}),
            'monthly_salary': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 60000', 'inputmode': 'decimal', 'autocomplete': 'off'}),
            'monthly_expenses': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 20000', 'inputmode': 'decimal', 'autocomplete': 'off'}),
            'existing_emi': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0', 'inputmode': 'decimal', 'autocomplete': 'off'}),
            'loan_amount': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 500000', 'inputmode': 'decimal', 'autocomplete': 'off'}),
            'tenure_months': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 36', 'inputmode': 'numeric', 'autocomplete': 'off'}),
            'interest_rate': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'e.g. 11.5 (leave blank for default)',
                'inputmode': 'decimal', 'autocomplete': 'off',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add empty "Select" as the first choice for loan_type
        self.fields['loan_type'].empty_label = None
        loan_type_choices = [('', 'Select Loan Type')] + list(self.fields['loan_type'].choices)
        self.fields['loan_type'].choices = loan_type_choices
        self.fields['loan_type'].initial = ''

    def clean_loan_type(self):
        lt = self.cleaned_data.get('loan_type')
        if not lt:
            raise forms.ValidationError("Please select a loan type.")
        return lt
