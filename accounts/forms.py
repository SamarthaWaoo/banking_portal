from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class RegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    email = forms.EmailField(required=True)
    pan_number = forms.CharField(
        max_length=10, required=True,
        widget=forms.TextInput(attrs={'placeholder': 'ABCDE1234F', 'style': 'text-transform:uppercase'})
    )
    aadhaar_number = forms.CharField(max_length=12, required=True)
    phone_number = forms.CharField(max_length=10, required=True)
    date_of_birth = forms.DateField(
        required=True, widget=forms.DateInput(attrs={'type': 'date'})
    )

    class Meta:
        model = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'pan_number', 'aadhaar_number', 'phone_number',
            'date_of_birth', 'password1', 'password2',
        ]

    def clean_pan_number(self):
        return self.cleaned_data['pan_number'].upper()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-control').strip()


class SetPinForm(forms.Form):
    pin = forms.CharField(
        max_length=4, min_length=4,
        widget=forms.PasswordInput(attrs={'inputmode': 'numeric', 'class': 'form-control', 'placeholder': '4-digit PIN'})
    )
    confirm_pin = forms.CharField(
        max_length=4, min_length=4,
        widget=forms.PasswordInput(attrs={'inputmode': 'numeric', 'class': 'form-control', 'placeholder': 'Re-enter PIN'})
    )

    def clean(self):
        cleaned = super().clean()
        pin = cleaned.get('pin')
        confirm = cleaned.get('confirm_pin')
        if pin and not pin.isdigit():
            raise forms.ValidationError("PIN must be numeric.")
        if pin and confirm and pin != confirm:
            raise forms.ValidationError("PINs do not match.")
        return cleaned
