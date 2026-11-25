
from functools import wraps

from django.http import JsonResponse
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST, require_GET

from .models import Booking
from .forms import BookingForm
from resources.models import Resource, Category
from maintenance.models import MaintenanceRecord


RETURN_CONDITIONS = {
    'EXCELLENT': 'Excellent',
    'GOOD': 'Good',
    'FAIR': 'Fair',
    'DAMAGED': 'Damaged',
}

ACTIVE_BOOKING_STATUSES = ['PENDING', 'APPROVED', 'ISSUED']


def has_role(user, roles):
    return user.is_superuser or (
        hasattr(user, 'profile') and user.profile.role in roles
    )


def role_required(role_check):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not role_check(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def can_manage_bookings(user):
    return has_role(user, ['STAFF', 'ADMIN'])


def can_book_resources(user):
    return has_role(user, ['STUDENT', 'FACULTY', 'ADMIN'])


def get_reserved_quantity(resource, start, end, exclude_booking_id=None):
    """
    Return the maximum number of units reserved simultaneously
    during the requested time interval.
    """
    bookings = Booking.objects.filter(
        resource=resource,
        start_datetime__lt=end,
        end_datetime__gt=start,
        status__in=ACTIVE_BOOKING_STATUSES
    )

    if exclude_booking_id is not None:
        bookings = bookings.exclude(pk=exclude_booking_id)

    events = []

    for booking in bookings:
        if booking.status == 'ISSUED':
            reserved_quantity = (
                booking.quantity - booking.returned_quantity
            )
        else:
            reserved_quantity = booking.quantity

        if reserved_quantity <= 0:
            continue

        effective_start = max(booking.start_datetime, start)
        effective_end = min(booking.end_datetime, end)

        events.append((effective_start, reserved_quantity))
        events.append((effective_end, -reserved_quantity))

    # Process end events before start events at the same timestamp.
    events.sort(key=lambda event: (event[0], event[1]))

    current_reserved = 0
    maximum_reserved = 0

    for event_time, change in events:
        current_reserved += change
        maximum_reserved = max(maximum_reserved, current_reserved)

    return maximum_reserved


def get_available_quantity(resource, start, end, exclude_booking_id=None):
    if resource.status != 'AVAILABLE':
        return 0

    if resource.tracking_type == 'INDIVIDUAL':
        conflicts = Booking.objects.filter(
            resource=resource,
            start_datetime__lt=end,
            end_datetime__gt=start,
            status__in=ACTIVE_BOOKING_STATUSES
        )

        if exclude_booking_id is not None:
            conflicts = conflicts.exclude(pk=exclude_booking_id)

        return 0 if conflicts.exists() else 1

    reserved = get_reserved_quantity(
        resource,
        start,
        end,
        exclude_booking_id
    )

    usable_stock = max(
        resource.total_quantity - resource.damaged_quantity,
        0
    )

    return max(usable_stock - reserved, 0)


@login_required
def resource_catalog(request):
    resources = Resource.objects.select_related(
        'category', 'location'
    ).filter(status='AVAILABLE')

    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    if query:
        resources = resources.filter(
            Q(name__icontains=query) |
            Q(asset_tag__icontains=query)
        )

    if category.isdigit():
        resources = resources.filter(category_id=int(category))

    if request.GET.get('ajax') == '1':
        resource_data = []

        for resource in resources:
            if resource.tracking_type == 'INDIVIDUAL':
                usable_quantity = 1
            else:
                usable_quantity = max(
                    resource.total_quantity - resource.damaged_quantity,
                    0
                )

            resource_data.append({
                'id': resource.id,
                'name': resource.name,
                'category': resource.category.name,
                'description': resource.description[:100],
                'asset_tag': resource.asset_tag or '',
                'location': resource.location.name,
                'condition': resource.get_condition_display(),
                'tracking_type': resource.tracking_type,
                'total_quantity': resource.total_quantity,
                'available_quantity': usable_quantity,
                'booking_url': reverse(
                    'create_booking_for_resource',
                    args=[resource.id]
                ),
            })

        return JsonResponse({'resources': resource_data})

    return render(request, 'bookings/resource_catalog.html', {
        'resources': resources,
        'categories': Category.objects.all(),
    })


@role_required(can_book_resources)
@require_GET
def check_booking_availability(request):
    resource_id = request.GET.get('resource')
    start_value = request.GET.get('start_datetime')
    end_value = request.GET.get('end_datetime')
    quantity_value = request.GET.get('quantity', '1')

    if not resource_id or not start_value or not end_value:
        return JsonResponse({
            'available': False,
            'message': 'Select a resource, start time and end time.'
        })

    if not resource_id.isdigit():
        return JsonResponse({
            'available': False,
            'message': 'Invalid resource selected.'
        })

    try:
        quantity = int(quantity_value)
        if quantity < 1:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({
            'available': False,
            'message': 'Enter a valid quantity.'
        })

    start = parse_datetime(start_value)
    end = parse_datetime(end_value)

    if not start or not end:
        return JsonResponse({
            'available': False,
            'message': 'Please enter valid date and time values.'
        })

    if timezone.is_naive(start):
        start = timezone.make_aware(start)

    if timezone.is_naive(end):
        end = timezone.make_aware(end)

    if start <= timezone.now():
        return JsonResponse({
            'available': False,
            'message': 'Booking start time must be in the future.'
        })

    if end <= start:
        return JsonResponse({
            'available': False,
            'message': 'End time must be after start time.'
        })

    try:
        resource = Resource.objects.get(pk=resource_id)
    except Resource.DoesNotExist:
        return JsonResponse({
            'available': False,
            'message': 'Resource not found.'
        })

    if resource.status != 'AVAILABLE':
        return JsonResponse({
            'available': False,
            'message': 'This resource is currently unavailable.'
        })

    if resource.tracking_type == 'INDIVIDUAL' and quantity != 1:
        return JsonResponse({
            'available': False,
            'message': 'Individual assets can only be booked one at a time.'
        })

    available = get_available_quantity(resource, start, end)

    if quantity > available:
        return JsonResponse({
            'available': False,
            'available_quantity': available,
            'message': (
                f'Only {available} units are available '
                f'for this time period.'
            )
        })

    return JsonResponse({
        'available': True,
        'available_quantity': available,
        'message': (
            f'{available} units are available for the selected time.'
        )
    })


@role_required(can_book_resources)
def create_booking(request, resource_id=None):
    initial = {}

    if resource_id:
        initial['resource'] = get_object_or_404(
            Resource,
            pk=resource_id,
            status='AVAILABLE'
        )

    form = BookingForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        booking = form.save(commit=False)
        booking.user = request.user

        with transaction.atomic():
            resource = get_object_or_404(
                Resource.objects.select_for_update(),
                pk=booking.resource_id
            )

            available = get_available_quantity(
                resource,
                booking.start_datetime,
                booking.end_datetime
            )

            if resource.status != 'AVAILABLE':
                form.add_error(
                    'resource',
                    'This resource is currently unavailable.'
                )

            elif (
                resource.tracking_type == 'INDIVIDUAL'
                and booking.quantity != 1
            ):
                form.add_error(
                    'quantity',
                    'Individual assets can only be booked one at a time.'
                )

            elif booking.quantity > available:
                form.add_error(
                    'quantity',
                    f'Only {available} units are available for this time period.'
                )

            else:
                booking.resource = resource
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
        'bookings': bookings,
        'now': timezone.now()
    })


@login_required
@require_POST
def cancel_booking(request, booking_id):
    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update(),
            pk=booking_id,
            user=request.user
        )

        if booking.status not in ['PENDING', 'APPROVED']:
            messages.error(
                request,
                'This booking can no longer be cancelled.'
            )

        elif booking.start_datetime <= timezone.now():
            messages.error(
                request,
                'A booking cannot be cancelled after its start time.'
            )

        else:
            booking.status = 'CANCELLED'
            booking.save(update_fields=['status'])

            messages.success(
                request,
                'Booking cancelled successfully.'
            )

    return redirect('my_bookings')


@role_required(can_manage_bookings)
def manage_bookings(request):
    bookings = Booking.objects.select_related(
        'user',
        'user__profile',
        'resource',
        'reviewed_by'
    ).all()

    for booking in bookings:
        booking.outstanding_quantity = (
            booking.quantity - booking.returned_quantity
        )

    return render(request, 'bookings/manage_bookings.html', {
        'bookings': bookings
    })


@role_required(can_manage_bookings)
@require_POST
def update_booking_status(request, booking_id):
    action = request.POST.get('action')

    with transaction.atomic():
        booking = get_object_or_404(
            Booking.objects.select_for_update().select_related('resource'),
            pk=booking_id
        )

        resource = Resource.objects.select_for_update().get(
            pk=booking.resource_id
        )

        if action == 'approve':

            if booking.status != 'PENDING':
                messages.error(
                    request,
                    'Only pending bookings can be approved.'
                )

            elif resource.status != 'AVAILABLE':
                messages.error(
                    request,
                    'This resource is currently unavailable.'
                )

            else:
                available = get_available_quantity(
                    resource,
                    booking.start_datetime,
                    booking.end_datetime,
                    exclude_booking_id=booking.pk
                )

                if booking.quantity > available:
                    messages.error(
                        request,
                        f'Cannot approve. Only {available} units remain available.'
                    )

                else:
                    booking.status = 'APPROVED'
                    booking.reviewed_by = request.user
                    booking.save(
                        update_fields=['status', 'reviewed_by']
                    )

                    messages.success(
                        request,
                        'Booking approved successfully.'
                    )

        elif action == 'reject':

            if booking.status != 'PENDING':
                messages.error(
                    request,
                    'Only pending bookings can be rejected.'
                )

            else:
                booking.status = 'REJECTED'
                booking.reviewed_by = request.user
                booking.save(
                    update_fields=['status', 'reviewed_by']
                )

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
                    update_fields=[
                        'status',
                        'issued_at',
                        'reviewed_by'
                    ]
                )

                messages.success(
                    request,
                    f'{booking.quantity} unit(s) marked as issued.'
                )

        elif action == 'return':

            if booking.status != 'ISSUED':
                messages.error(
                    request,
                    'Only issued resources can be returned.'
                )

            else:
                outstanding = (
                    booking.quantity - booking.returned_quantity
                )

                try:
                    return_quantity = int(
                        request.POST.get(
                            'return_quantity',
                            outstanding
                        )
                    )

                    damaged_quantity = int(
                        request.POST.get(
                            'damaged_quantity',
                            '0'
                        )
                    )

                except (TypeError, ValueError):
                    return_quantity = 0
                    damaged_quantity = -1

                return_condition = request.POST.get(
                    'return_condition',
                    'GOOD'
                ).strip().upper()

                if return_quantity < 1 or return_quantity > outstanding:
                    messages.error(
                        request,
                        f'Enter a return quantity between 1 and {outstanding}.'
                    )

                elif damaged_quantity < 0 or damaged_quantity > return_quantity:
                    messages.error(
                        request,
                        'Damaged quantity cannot exceed the returned quantity.'
                    )

                elif return_condition not in RETURN_CONDITIONS:
                    messages.error(
                        request,
                        'Please select a valid return condition.'
                    )

                else:
                    if return_condition == 'DAMAGED' and damaged_quantity == 0:
                        damaged_quantity = return_quantity

                    booking.returned_quantity += return_quantity
                    booking.damaged_quantity += damaged_quantity
                    booking.return_condition = RETURN_CONDITIONS[
                        return_condition
                    ]
                    booking.reviewed_by = request.user

                    if booking.returned_quantity == booking.quantity:
                        booking.status = 'RETURNED'
                        booking.returned_at = timezone.now()

                    booking.save(
                        update_fields=[
                            'returned_quantity',
                            'damaged_quantity',
                            'return_condition',
                            'reviewed_by',
                            'status',
                            'returned_at'
                        ]
                    )

                    if damaged_quantity > 0:
                        resource.damaged_quantity += damaged_quantity

                        if resource.tracking_type == 'INDIVIDUAL':
                            resource.condition = 'DAMAGED'
                            resource.status = 'MAINTENANCE'

                        else:
                            usable_stock = max(
                                resource.total_quantity -
                                resource.damaged_quantity,
                                0
                            )

                            if resource.status != 'UNAVAILABLE':
                                resource.status = (
                                    'AVAILABLE'
                                    if usable_stock > 0
                                    else 'MAINTENANCE'
                                )

                        resource.save(
                            update_fields=[
                                'damaged_quantity',
                                'condition',
                                'status'
                            ]
                        )

                        MaintenanceRecord.objects.create(
                            resource=resource,
                            reported_by=request.user,
                            quantity_affected=damaged_quantity,
                            stock_deducted=True,
                            issue_description=(
                                f'{damaged_quantity} unit(s) of '
                                f'{resource.name} were returned damaged '
                                f'under booking #{booking.pk}. '
                                f'Inspection and repair required.'
                            )
                        )

                    messages.success(
                        request,
                        f'{return_quantity} unit(s) returned successfully. '
                        f'{damaged_quantity} damaged.'
                    )

        else:
            messages.error(request, 'Invalid booking action.')

    return redirect('manage_bookings')
