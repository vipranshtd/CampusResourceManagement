
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

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

        if booking.resource.status != 'AVAILABLE':
            form.add_error('resource', 'This resource is not available.')
        else:
            with transaction.atomic():
                conflicts = Booking.objects.select_for_update().filter(
                    resource=booking.resource,
                    start_datetime__lt=booking.end_datetime,
                    end_datetime__gt=booking.start_datetime
                ).exclude(status__in=['REJECTED', 'CANCELLED'])

                if conflicts.exists():
                    form.add_error(
                        None,
                        'This resource is already booked during that time.'
                    )
                else:
                    booking.save()
                    messages.success(request, 'Booking request submitted.')
                    return redirect('my_bookings')

    return render(request, 'bookings/booking_form.html', {
        'form': form
    })


@login_required
def my_bookings(request):
    bookings = Booking.objects.select_related(
        'resource', 'resource__category', 'resource__location'
    ).filter(user=request.user)

    return render(request, 'bookings/my_bookings.html', {
        'bookings': bookings
    })


@login_required
@user_passes_test(can_manage_bookings)
def manage_bookings(request):
    bookings = Booking.objects.select_related(
        'user', 'resource'
    ).all()

    return render(request, 'bookings/manage_bookings.html', {
        'bookings': bookings
    })


@login_required
@user_passes_test(can_manage_bookings)
def update_booking_status(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve' and booking.status == 'PENDING':
            with transaction.atomic():
                conflicts = Booking.objects.select_for_update().filter(
                    resource=booking.resource,
                    start_datetime__lt=booking.end_datetime,
                    end_datetime__gt=booking.start_datetime,
                    status__in=['APPROVED', 'ISSUED']
                ).exclude(pk=booking.pk)

                if conflicts.exists():
                    messages.error(
                        request,
                        'Cannot approve: another booking occupies this slot.'
                    )
                else:
                    booking.status = 'APPROVED'
                    booking.reviewed_by = request.user
                    booking.save()
                    messages.success(request, 'Booking approved.')

        elif action == 'reject' and booking.status == 'PENDING':
            booking.status = 'REJECTED'
            booking.reviewed_by = request.user
            booking.save()
            messages.success(request, 'Booking rejected.')

    return redirect('manage_bookings')
