
from functools import wraps
from django.http import JsonResponse
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET


from .models import Booking
from .forms import BookingForm
from resources.models import Resource
from maintenance.models import MaintenanceRecord

from django.db.models import Q
from resources.models import Resource, Category

RETURN_CONDITIONS = {
    'EXCELLENT': 'Excellent',
    'GOOD': 'Good',
    'FAIR': 'Fair',
    'DAMAGED': 'Damaged',
}


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
            resource_data.append({
                'id': resource.id,
                'name': resource.name,
                'category': resource.category.name,
                'description': resource.description[:100],
                'asset_tag': resource.asset_tag,
                'location': resource.location.name,
                'condition': resource.get_condition_display(),
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
        resource = Resource.objects.get(
            pk=resource_id,
            status='AVAILABLE'
        )
    except Resource.DoesNotExist:
        return JsonResponse({
            'available': False,
            'message': 'This resource is currently unavailable.'
        })

    conflicts = Booking.objects.filter(
        resource=resource,
        start_datetime__lt=end,
        end_datetime__gt=start,
        status__in=['PENDING', 'APPROVED', 'ISSUED']
    )

    if conflicts.exists():
        return JsonResponse({
            'available': False,
            'message': 'This resource is already booked during the selected time.'
        })

    return JsonResponse({
        'available': True,
        'message': 'Great! This resource is available for the selected time.'
    })


@role_required(can_book_resources)
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
            messages.success(request, 'Booking cancelled successfully.')

    return redirect('my_bookings')


@role_required(can_manage_bookings)
def manage_bookings(request):
    bookings = Booking.objects.select_related(
        'user',
        'resource',
        'reviewed_by'
    ).all()

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
                conflicts = Booking.objects.filter(
                    resource=resource,
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
                booking.save(update_fields=['status', 'reviewed_by'])
                messages.success(request, 'Booking rejected.')

        elif action == 'issue':
            if booking.status != 'APPROVED':
                messages.error(
                    request,
                    'Only approved bookings can be marked as issued.'
                )
            elif resource.status != 'AVAILABLE':
                messages.error(
                    request,
                    'This resource is currently unavailable.'
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
                    'Resource marked as issued.'
                )

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

                if return_condition not in RETURN_CONDITIONS:
                    messages.error(
                        request,
                        'Please select a valid return condition.'
                    )
                else:
                    booking.status = 'RETURNED'
                    booking.returned_at = timezone.now()
                    booking.return_condition = RETURN_CONDITIONS[
                        return_condition
                    ]
                    booking.reviewed_by = request.user

                    booking.save(
                        update_fields=[
                            'status',
                            'returned_at',
                            'return_condition',
                            'reviewed_by'
                        ]
                    )

                    resource.condition = return_condition

                    if return_condition == 'DAMAGED':
                        resource.status = 'MAINTENANCE'
                        MaintenanceRecord.objects.create(
                            resource=resource,
                            reported_by=request.user,
                            issue_description=(
                                f'Resource returned in damaged condition '
                                f'under booking #{booking.pk}. '
                                f'Inspection and repair required.'
                            )
                        )

                    resource.save(update_fields=['condition', 'status'])

                    messages.success(
                        request,
                        'Resource return recorded successfully.'
                    )

        else:
            messages.error(request, 'Invalid booking action.')

    return redirect('manage_bookings')
