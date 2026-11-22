
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.views.decorators.http import require_POST

from .models import Resource, Category
from .forms import ResourceForm


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
