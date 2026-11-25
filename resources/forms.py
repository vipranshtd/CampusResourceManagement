
from django import forms
from .models import Resource, Category, Location


class ResourceForm(forms.ModelForm):

    class Meta:
        model = Resource
        fields = [
            'name',
            'tracking_type',
            'asset_tag',
            'total_quantity',
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
            'tracking_type': forms.Select(),
            'asset_tag': forms.TextInput(attrs={
                'placeholder': 'Enter unique asset tag'
            }),
            'total_quantity': forms.NumberInput(attrs={
                'min': 1,
                'placeholder': 'Enter total quantity'
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
            'tracking_type': 'Inventory Type',
            'asset_tag': 'Asset Tag',
            'total_quantity': 'Total Stock Quantity',
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

        self.fields['asset_tag'].required = False
        self.fields['total_quantity'].min_value = 1

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_asset_tag(self):
        asset_tag = (self.cleaned_data.get('asset_tag') or '').strip()
        return asset_tag or None

    def clean(self):
        cleaned_data = super().clean()

        tracking_type = cleaned_data.get('tracking_type')
        asset_tag = cleaned_data.get('asset_tag')
        total_quantity = cleaned_data.get('total_quantity')

        if tracking_type == 'INDIVIDUAL':
            if not asset_tag:
                self.add_error(
                    'asset_tag',
                    'Asset tag is required for individual assets.'
                )

            cleaned_data['total_quantity'] = 1

        elif tracking_type == 'QUANTITY':
            cleaned_data['asset_tag'] = None

            if total_quantity is not None and total_quantity < 1:
                self.add_error(
                    'total_quantity',
                    'Total quantity must be at least 1.'
                )

            if (
                total_quantity is not None
                and self.instance.pk
                and total_quantity < self.instance.damaged_quantity
            ):
                self.add_error(
                    'total_quantity',
                    'Total quantity cannot be less than the damaged stock.'
                )

        if asset_tag:
            existing = Resource.objects.filter(
                asset_tag__iexact=asset_tag
            )

            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                self.add_error(
                    'asset_tag',
                    'A resource with this asset tag already exists.'
                )

        return cleaned_data
