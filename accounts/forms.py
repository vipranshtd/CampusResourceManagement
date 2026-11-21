from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile

class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    enrollment_number = forms.CharField(max_length=20, required=True)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'enrollment_number', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
    
    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        if not email.endswith('@mail.jiit.ac.in'):
            raise forms.ValidationError("Only JIIT college email addresses are allowed.")

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")

        return email

    def clean_enrollment_number(self):
        enrollment = self.cleaned_data['enrollment_number'].strip()

        if Profile.objects.filter(enrollment_number=enrollment).exists():
            raise forms.ValidationError("This enrollment number is already registered.")

        return enrollment