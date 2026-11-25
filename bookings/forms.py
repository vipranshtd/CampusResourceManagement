
from django import forms
from django.utils import timezone

from .models import Booking
from resources.models import Resource


class BookingForm(forms.ModelForm):

    class Meta:
        model = Booking
        fields = [
            'resource',
            'quantity',
            'start_datetime',
            'end_datetime',
            'purpose'
        ]

        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'value': 1
            }),
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

        self.fields['quantity'].help_text = (
            'Individual assets allow one unit per booking. '
            'Quantity-based resources allow multiple units.'
        )

        self.fields['quantity'].min_value = 1

        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def get_reserved_quantity(self, resource, start, end):
        bookings = Booking.objects.filter(
            resource=resource,
            start_datetime__lt=end,
            end_datetime__gt=start,
            status__in=['PENDING', 'APPROVED', 'ISSUED']
        )

        events = []

        for booking in bookings:
            reserved_quantity = (
                booking.quantity - booking.returned_quantity
                if booking.status == 'ISSUED'
                else booking.quantity
            )

            if reserved_quantity <= 0:
                continue

            effective_start = max(booking.start_datetime, start)
            effective_end = min(booking.end_datetime, end)

            events.append((effective_start, reserved_quantity))
            events.append((effective_end, -reserved_quantity))

        events.sort(key=lambda event: (event[0], event[1]))

        current_reserved = 0
        maximum_reserved = 0

        for event_time, change in events:
            current_reserved += change
            maximum_reserved = max(
                maximum_reserved,
                current_reserved
            )

        return maximum_reserved

    def clean(self):
        cleaned_data = super().clean()

        resource = cleaned_data.get('resource')
        quantity = cleaned_data.get('quantity')
        start = cleaned_data.get('start_datetime')
        end = cleaned_data.get('end_datetime')

        if quantity is not None and quantity < 1:
            self.add_error(
                'quantity',
                'Quantity must be at least 1.'
            )

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

        if not (resource and quantity and start and end and end > start):
            return cleaned_data

        if resource.status != 'AVAILABLE':
            self.add_error(
                'resource',
                'This resource is currently unavailable.'
            )
            return cleaned_data

        if resource.tracking_type == 'INDIVIDUAL':

            if quantity != 1:
                self.add_error(
                    'quantity',
                    'Individual assets can only be booked one at a time.'
                )
                return cleaned_data

            conflicts = Booking.objects.filter(
                resource=resource,
                start_datetime__lt=end,
                end_datetime__gt=start,
                status__in=['PENDING', 'APPROVED', 'ISSUED']
            )

            if conflicts.exists():
                self.add_error(
                    'resource',
                    'This individual asset is already booked during '
                    'the selected time.'
                )

        elif resource.tracking_type == 'QUANTITY':

            usable_stock = max(
                resource.total_quantity - resource.damaged_quantity,
                0
            )

            if quantity > usable_stock:
                self.add_error(
                    'quantity',
                    f'Only {usable_stock} usable units exist.'
                )
                return cleaned_data

            reserved = self.get_reserved_quantity(
                resource,
                start,
                end
            )

            remaining = max(usable_stock - reserved, 0)

            if quantity > remaining:
                self.add_error(
                    'quantity',
                    f'Only {remaining} units are available '
                    'for the selected time period.'
                )

        return cleaned_data
