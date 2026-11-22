
from django import forms
from django.utils import timezone
from .models import Booking
from resources.models import Resource




class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            'resource',
            'start_datetime',
            'end_datetime',
            'purpose'
        ]

        widgets = {
            'start_datetime': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-control'
                }
            ),
            'end_datetime': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'form-control'
                }
            ),
            'purpose': forms.Textarea(
                attrs={
                    'rows': 3,
                    'placeholder': 'Explain why you need this resource...',
                    'class': 'form-control'
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['resource'].queryset = Resource.objects.filter(
            status='AVAILABLE'
        )

        self.fields['resource'].empty_label = 'Select a resource'

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()

        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')

        if start and end:
            if start <= timezone.now():
                self.add_error(
                    'start_datetime',
                    'Booking must be in the future.'
                )

            if end <= start:
                self.add_error(
                    'end_datetime',
                    'End time must be after start time.'
                )

        return cleaned_data
