
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Booking
from .forms import BookingForm
from resources.models import Resource


def can_manage_bookings(user):
    return user.is_superuser or (
        hasattr(user, 'profile') and
        user.profile.role in ['STAFF', 'ADMIN']
    )


@login_required
def resource_catalog(request):
    resources = Resource.objects.select_related(
        'category', 'location'
    ).filter(status='AVAILABLE')

    return render(request, 'bookings/resource_catalog.html', {
        'resources': resources
    })


@login_required
def create_booking(request, resource_id=None):
    initial = {}

    if resource_id:
        initial['resource'] = get_object_or_404(
            Resource, pk=resource_id, status='AVAILABLE'
        )

    form = BookingForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        booking = form.save(commit=False)
        booking.user = request.user

        with transaction.atomic():
            try:
                resource = Resource.objects.select_for_update().get(
                    pk=booking.resource_id,
                    status='AVAILABLE'
                )
            except Resource.DoesNotExist:
                form.add_error(
                    'resource',
                    'This resource is not available.'
                )
            else:
                booking.resource = resource

                conflicts = Booking.objects.filter(
                    resource=resource,
                    start_datetime__lt=booking.end_datetime,
                    end_datetime__gt=booking.start_datetime,
                    status__in=['PENDING', 'APPROVED', 'ISSUED']
                )

                if conflicts.exists():
                    form.add_error(
                        None,
                        'This resource is already booked during that time.'
                    )
                else:
                    booking.save()
                    messages.success(
                        request,
                        'Booking request submitted successfully.'
                    )
                    return redirect('my_bookings')

    return render(request, 'bookings/booking_form.html', {
        'form': form
    })


@login_required
def my_bookings(request):
    bookings = Booking.objects.select_related(
        'resource',
        'resource__category',
        'resource__location',
        'reviewed_by'
    ).filter(user=request.user)

    return render(request, 'bookings/my_bookings.html', {
        'bookings': bookings
    })


@login_required
@user_passes_test(can_manage_bookings)
def manage_bookings(request):
    bookings = Booking.objects.select_related(
        'user',
        'resource',
        'reviewed_by'
    ).all()

    return render(request, 'bookings/manage_bookings.html', {
        'bookings': bookings
    })


@login_required
@user_passes_test(can_manage_bookings)
@require_POST
def update_booking_status(request, booking_id):
    action = request.POST.get('action')
    booking = get_object_or_404(
        Booking.objects.select_related('resource'),
        pk=booking_id
    )

    if action == 'approve':
        if booking.status != 'PENDING':
            messages.error(request, 'This booking cannot be approved.')
            return redirect('manage_bookings')

        with transaction.atomic():
            Resource.objects.select_for_update().get(
                pk=booking.resource_id
            )

            conflicts = Booking.objects.filter(
                resource=booking.resource,
                start_datetime__lt=booking.end_datetime,
                end_datetime__gt=booking.start_datetime,
                status__in=['APPROVED', 'ISSUED']
            ).exclude(pk=booking.pk)

            if conflicts.exists():
                messages.error(
                    request,
                    'Cannot approve: another approved booking occupies this slot.'
                )
            else:
                booking.status = 'APPROVED'
                booking.reviewed_by = request.user
                booking.save(update_fields=['status', 'reviewed_by'])
                messages.success(request, 'Booking approved successfully.')

    elif action == 'reject':
        if booking.status != 'PENDING':
            messages.error(request, 'Only pending bookings can be rejected.')
        else:
            booking.status = 'REJECTED'
            booking.reviewed_by = request.user
            booking.save(update_fields=['status', 'reviewed_by'])
            messages.success(request, 'Booking rejected.')

    elif action == 'issue':
        if booking.status != 'APPROVED':
            messages.error(
                request,
                'Only approved bookings can be marked as issued.'
            )
        else:
            booking.status = 'ISSUED'
            booking.issued_at = timezone.now()
            booking.reviewed_by = request.user
            booking.save(
                update_fields=['status', 'issued_at', 'reviewed_by']
            )
            messages.success(request, 'Resource marked as issued.')

    elif action == 'return':
        if booking.status != 'ISSUED':
            messages.error(
                request,
                'Only issued resources can be marked as returned.'
            )
        else:
            return_condition = request.POST.get(
                'return_condition', ''
            ).strip()

            if not return_condition:
                messages.error(
                    request,
                    'Please enter the condition of the returned resource.'
                )
            else:
                booking.status = 'RETURNED'
                booking.returned_at = timezone.now()
                booking.return_condition = return_condition
                booking.reviewed_by = request.user
                booking.save(
                    update_fields=[
                        'status',
                        'returned_at',
                        'return_condition',
                        'reviewed_by'
                    ]
                )
                messages.success(
                    request,
                    'Resource return recorded successfully.'
                )

    else:
        messages.error(request, 'Invalid booking action.')

    return redirect('manage_bookings')
