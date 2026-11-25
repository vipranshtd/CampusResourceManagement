
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile


class RegistrationForm(UserCreationForm):

    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)

    institutional_id = forms.CharField(
        max_length=30,
        required=True,
        label='Enrollment / Employee ID'
    )

    requested_role = forms.ChoiceField(
        choices=[
            ('STUDENT', 'Student'),
            ('FACULTY', 'Faculty'),
            ('STAFF', 'Resource Staff'),
        ],
        required=True,
        label='Registering as'
    )

    class Meta:
        model = User
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'institutional_id',
            'requested_role',
            'password1',
            'password2'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

        self.fields['username'].help_text = 'Choose a unique username.'
        self.fields['email'].help_text = 'Use your JIIT college email address.'
        self.fields['institutional_id'].help_text = (
            'Enter your JIIT enrollment or employee ID.'
        )

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()

        if not email.endswith('@mail.jiit.ac.in'):
            raise forms.ValidationError(
                "Only JIIT college email addresses are allowed."
            )

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "This email is already registered."
            )

        return email

    def clean_institutional_id(self):
        institutional_id = self.cleaned_data['institutional_id'].strip()

        if Profile.objects.filter(
            institutional_id__iexact=institutional_id
        ).exists():
            raise forms.ValidationError(
                "This institutional ID is already registered."
            )

        return institutional_id
