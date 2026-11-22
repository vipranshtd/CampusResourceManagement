
from django import forms
from .models import Resource, Category, Location


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        fields = [
            'name',
            'asset_tag',
            'category',
            'location',
            'description',
            'status',
            'condition'
        ]

        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'Enter resource name'
            }),
            'asset_tag': forms.TextInput(attrs={
                'placeholder': 'Enter unique asset tag'
            }),
            'category': forms.Select(),
            'location': forms.Select(),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Describe the resource and its purpose'
            }),
            'status': forms.Select(),
            'condition': forms.Select(),
        }

        labels = {
            'name': 'Resource Name',
            'asset_tag': 'Asset Tag',
            'category': 'Category',
            'location': 'Campus Location',
            'description': 'Description',
            'status': 'Availability Status',
            'condition': 'Physical Condition',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['category'].queryset = Category.objects.all().order_by('name')
        self.fields['location'].queryset = Location.objects.all().order_by('name')

        self.fields['category'].empty_label = 'Select a category'
        self.fields['location'].empty_label = 'Select a location'

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_asset_tag(self):
        asset_tag = self.cleaned_data['asset_tag'].strip()

        existing = Resource.objects.filter(
            asset_tag__iexact=asset_tag
        )

        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise forms.ValidationError(
                'A resource with this asset tag already exists.'
            )

        return asset_tag
