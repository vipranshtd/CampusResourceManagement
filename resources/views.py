
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum, F
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST

from .models import Resource, Category
from .forms import ResourceForm
from bookings.models import Booking


def can_manage_resources(user):
    return user.is_superuser or (
        hasattr(user, 'profile') and
        user.profile.role in ['STAFF', 'ADMIN']
    )


def resource_manager_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_manage_resources(request.user):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper


@resource_manager_required
def resource_list(request):
    resources = Resource.objects.select_related(
        'category', 'location'
    ).all()

    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip()

    if query:
        resources = resources.filter(
            Q(name__icontains=query) |
            Q(asset_tag__icontains=query)
        )

    if category:
        resources = resources.filter(category_id=category)

    valid_statuses = [
        choice[0] for choice in Resource.STATUS_CHOICES
    ]

    if status in valid_statuses:
        resources = resources.filter(status=status)

    context = {
        'resources': resources,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': category,
        'selected_status': status,
    }

    return render(request, 'resources/resource_list.html', context)


@resource_manager_required
def inventory_overview(request):
    all_resources = list(
        Resource.objects.select_related(
            'category', 'location'
        ).all()
    )

    issued_bookings = Booking.objects.filter(
        status='ISSUED'
    ).values('resource_id').annotate(
        issued_quantity=Sum(
            F('quantity') - F('returned_quantity')
        )
    )

    issued_map = {
        item['resource_id']: item['issued_quantity'] or 0
        for item in issued_bookings
    }

    total_resources = len(all_resources)
    total_units = 0
    usable_units = 0
    available_units = 0
    issued_units = 0
    damaged_units = 0

    unavailable_count = 0
    maintenance_count = 0

    category_summary = {}
    location_summary = {}

    for resource in all_resources:

        if resource.tracking_type == 'INDIVIDUAL':
            resource_total = 1
        else:
            resource_total = resource.total_quantity

        resource_damaged = min(
            resource.damaged_quantity,
            resource_total
        )

        resource_usable = max(
            resource_total - resource_damaged,
            0
        )

        resource_issued = issued_map.get(resource.id, 0)

        if resource.tracking_type == 'INDIVIDUAL':
            resource_issued = min(resource_issued, 1)

        resource_available = (
            max(resource_usable - resource_issued, 0)
            if resource.status == 'AVAILABLE'
            else 0
        )

        resource.inventory_total = resource_total
        resource.inventory_usable = resource_usable
        resource.inventory_issued = resource_issued
        resource.inventory_damaged = resource_damaged
        resource.inventory_available = resource_available

        if (
            resource.status == 'AVAILABLE'
            and resource_usable > 0
            and resource_issued >= resource_usable
            and resource_issued > 0
        ):
            resource.inventory_status = 'ISSUED'
        else:
            resource.inventory_status = resource.status

        total_units += resource_total
        usable_units += resource_usable
        available_units += resource_available
        issued_units += resource_issued
        damaged_units += resource_damaged

        if resource.status == 'UNAVAILABLE':
            unavailable_count += 1

        elif resource.status == 'MAINTENANCE':
            maintenance_count += 1

        category_id = resource.category_id

        if category_id not in category_summary:
            category_summary[category_id] = {
                'name': resource.category.name,
                'resource_count': 0,
                'unit_count': 0,
            }

        category_summary[category_id]['resource_count'] += 1
        category_summary[category_id]['unit_count'] += resource_total

        location_key = resource.location_id

        if location_key not in location_summary:
            location_summary[location_key] = {
                'location__name': resource.location.name,
                'location__building': resource.location.building,
                'resource_count': 0,
                'unit_count': 0,
            }

        location_summary[location_key]['resource_count'] += 1
        location_summary[location_key]['unit_count'] += resource_total

    # Search and filters
    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip()

    resources = all_resources

    if query:
        query_lower = query.lower()

        resources = [
            resource for resource in resources
            if query_lower in resource.name.lower()
            or query_lower in (resource.asset_tag or '').lower()
        ]

    if category.isdigit():
        resources = [
            resource for resource in resources
            if resource.category_id == int(category)
        ]
    else:
        category = ''

    valid_statuses = [
        'AVAILABLE',
        'ISSUED',
        'UNAVAILABLE',
        'MAINTENANCE',
    ]

    if status in valid_statuses:
        resources = [
            resource for resource in resources
            if resource.inventory_status == status
        ]
    else:
        status = ''

    resources.sort(key=lambda resource: resource.name.lower())

    category_data = sorted(
        category_summary.values(),
        key=lambda item: item['resource_count'],
        reverse=True
    )

    location_data = sorted(
        location_summary.values(),
        key=lambda item: item['resource_count'],
        reverse=True
    )

    context = {
        'total_resources': total_resources,
        'total_units': total_units,
        'usable_units': usable_units,
        'available_count': available_units,
        'issued_count': issued_units,
        'damaged_units': damaged_units,
        'unavailable_count': unavailable_count,
        'maintenance_count': maintenance_count,
        'category_data': category_data,
        'location_data': location_data,
        'resources': resources,
        'categories': Category.objects.all(),
        'query': query,
        'selected_category': category,
        'selected_status': status,
    }

    return render(
        request,
        'resources/inventory_overview.html',
        context
    )


@resource_manager_required
def resource_create(request):
    form = ResourceForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        resource = form.save()

        messages.success(
            request,
            f'{resource.name} has been added successfully.'
        )

        return redirect('resource_list')

    return render(request, 'resources/resource_form.html', {
        'form': form,
        'title': 'Add Resource'
    })


@resource_manager_required
def resource_update(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    form = ResourceForm(request.POST or None, instance=resource)

    if request.method == 'POST' and form.is_valid():
        resource = form.save()

        messages.success(
            request,
            f'{resource.name} has been updated successfully.'
        )

        return redirect('resource_list')

    return render(request, 'resources/resource_form.html', {
        'form': form,
        'title': 'Update Resource'
    })


@resource_manager_required
@require_POST
def resource_delete(request, pk):
    resource = get_object_or_404(Resource, pk=pk)
    resource_name = resource.name

    try:
        resource.delete()

        messages.success(
            request,
            f'{resource_name} has been deleted successfully.'
        )

    except ProtectedError:
        messages.error(
            request,
            'This resource cannot be deleted because it is linked '
            'to existing bookings or maintenance records. '
            'You can mark it as unavailable instead.'
        )

    return redirect('resource_list')
