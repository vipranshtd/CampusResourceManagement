
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import (
    Q, Count, Exists, OuterRef, Case, When, Value, CharField, F
)
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
    issued_bookings = Booking.objects.filter(
        resource_id=OuterRef('pk'),
        status='ISSUED'
    )

    all_resources = Resource.objects.select_related(
        'category', 'location'
    ).annotate(
        is_issued=Exists(issued_bookings)
    ).annotate(
        inventory_status=Case(
            When(is_issued=True, then=Value('ISSUED')),
            default=F('status'),
            output_field=CharField()
        )
    )

    total_resources = all_resources.count()

    issued_count = all_resources.filter(
        inventory_status='ISSUED'
    ).count()

    available_count = all_resources.filter(
        inventory_status='AVAILABLE'
    ).count()

    unavailable_count = all_resources.filter(
        inventory_status='UNAVAILABLE'
    ).count()

    maintenance_count = all_resources.filter(
        inventory_status='MAINTENANCE'
    ).count()

    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()
    status = request.GET.get('status', '').strip()

    resources = all_resources

    if query:
        resources = resources.filter(
            Q(name__icontains=query) |
            Q(asset_tag__icontains=query)
        )

    if category.isdigit():
        resources = resources.filter(category_id=int(category))
    else:
        category = ''

    valid_statuses = [
        'AVAILABLE',
        'ISSUED',
        'UNAVAILABLE',
        'MAINTENANCE'
    ]

    if status in valid_statuses:
        resources = resources.filter(inventory_status=status)
    else:
        status = ''

    category_data = Category.objects.annotate(
        resource_count=Count('resources')
    ).order_by('-resource_count', 'name')

    location_data = all_resources.values(
        'location__name',
        'location__building'
    ).annotate(
        resource_count=Count('id')
    ).order_by('-resource_count')

    context = {
        'total_resources': total_resources,
        'available_count': available_count,
        'issued_count': issued_count,
        'unavailable_count': unavailable_count,
        'maintenance_count': maintenance_count,
        'category_data': category_data,
        'location_data': location_data,
        'resources': resources.order_by('name'),
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
