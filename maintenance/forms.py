
from django import forms
from .models import MaintenanceRecord
from resources.models import Resource


class MaintenanceRecordForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = [
            'resource',
            'issue_description'
        ]

        widgets = {
            'resource': forms.Select(),
            'issue_description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe the problem, damage or malfunction in detail...'
            }),
        }

        labels = {
            'resource': 'Select Resource',
            'issue_description': 'Describe the Issue',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['resource'].queryset = Resource.objects.select_related(
            'category', 'location'
        ).order_by('name')

        self.fields['resource'].empty_label = 'Choose a campus resource'

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
