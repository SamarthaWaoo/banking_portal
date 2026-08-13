from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


# ── Shared eye-toggle widget mixin ──────────────────────────────────
def _password_input(placeholder='', extra_class=''):
    return forms.PasswordInput(attrs={
        'class': f'form-control {extra_class}'.strip(),
        'placeholder': placeholder,
    })


class RegisterForm(UserCreationForm):
    first_name    = forms.CharField(max_length=30, required=True)
    last_name     = forms.CharField(max_length=30, required=True)
    email         = forms.EmailField(required=True)
    pan_number    = forms.CharField(
        max_length=10, required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'ABCDE1234F',
            'style': 'text-transform:uppercase',
            'class': 'form-control',
        })
    )
    aadhaar_number = forms.CharField(
        max_length=12, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '12-digit number'})
    )
    phone_number   = forms.CharField(
        max_length=10, required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit mobile'})
    )
    date_of_birth  = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model  = CustomUser
        fields = [
            'username', 'first_name', 'last_name', 'email',
            'pan_number', 'aadhaar_number', 'phone_number',
            'date_of_birth', 'password1', 'password2',
        ]

    def clean_pan_number(self):
        return self.cleaned_data['pan_number'].upper()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add form-control to every field that doesn't already have it
        for name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'
            elif 'form-control' not in field.widget.attrs['class']:
                field.widget.attrs['class'] += ' form-control'


class SetPinForm(forms.Form):
    pin = forms.CharField(
        max_length=4, min_length=4,
        widget=forms.PasswordInput(attrs={
            'inputmode': 'numeric',
            'class': 'form-control pin-input',
            'placeholder': '• • • •',
            'maxlength': '4',
            'autocomplete': 'new-password',
        })
    )
    confirm_pin = forms.CharField(
        max_length=4, min_length=4,
        widget=forms.PasswordInput(attrs={
            'inputmode': 'numeric',
            'class': 'form-control pin-input',
            'placeholder': '• • • •',
            'maxlength': '4',
            'autocomplete': 'new-password',
        })
    )

    def clean(self):
        cleaned = super().clean()
        pin     = cleaned.get('pin', '')
        confirm = cleaned.get('confirm_pin', '')
        if pin and not pin.isdigit():
            raise forms.ValidationError("PIN must be numeric.")
        if pin and confirm and pin != confirm:
            raise forms.ValidationError("PINs do not match.")
        return cleaned


class AdminRegisterForm(UserCreationForm):
    """Minimal form for creating an admin/staff account."""
    first_name = forms.CharField(max_length=30, required=True,
                                 widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name  = forms.CharField(max_length=30, required=True,
                                 widget=forms.TextInput(attrs={'class': 'form-control'}))
    email      = forms.EmailField(required=True,
                                  widget=forms.EmailInput(attrs={'class': 'form-control'}))
    # Admins don't need PAN/Aadhaar — use dummy values
    pan_number     = forms.CharField(max_length=10, required=False,
                                     widget=forms.HiddenInput(), initial='ADMIN0000A')
    aadhaar_number = forms.CharField(max_length=12, required=False,
                                     widget=forms.HiddenInput(), initial='000000000000')
    phone_number   = forms.CharField(max_length=10, required=True,
                                     widget=forms.TextInput(attrs={'class': 'form-control',
                                                                    'placeholder': '10-digit mobile'}))

    class Meta:
        model  = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if hasattr(field.widget, 'attrs') and 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        import hashlib
        user = super().save(commit=False)
        # Set dummy KYC values for admin accounts (not validated).
        # PAN: 10 chars, Aadhaar: 12 unique digits derived from username hash
        # so a second admin doesn't hit the UNIQUE constraint.
        user.pan_number = (f"ADM{user.username[:5].upper()}0000A")[:10]
        digest = hashlib.md5(user.username.encode()).hexdigest()
        user.aadhaar_number = str(int(digest[:15], 16))[:12].zfill(12)
        if commit:
            user.save()
        return user
