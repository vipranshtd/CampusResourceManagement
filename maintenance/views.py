
from functools import wraps

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import MaintenanceRecord
from .forms import MaintenanceRecordForm
from resources.models import Resource


def can_manage_maintenance(user):
    return user.is_superuser or (
        hasattr(user, 'profile') and
        user.profile.role in ['STAFF', 'ADMIN']
    )


def maintenance_manager_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_manage_maintenance(request.user):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper


@login_required
def maintenance_list(request):
    records = MaintenanceRecord.objects.select_related(
        'resource', 'reported_by'
    ).order_by('-reported_at')

    can_manage = can_manage_maintenance(request.user)

    if not can_manage:
        records = records.filter(reported_by=request.user)

    return render(request, 'maintenance/maintenance_list.html', {
        'records': records,
        'can_manage': can_manage,
    })


@login_required
def report_maintenance(request):
    form = MaintenanceRecordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = form.save(commit=False)
            record.reported_by = request.user

            resource = Resource.objects.select_for_update().get(
                pk=record.resource_id
            )

            record.save()

            if resource.status != 'MAINTENANCE':
                resource.status = 'MAINTENANCE'
                resource.save(update_fields=['status'])

        messages.success(
            request,
            'Maintenance issue reported successfully.'
        )
        return redirect('maintenance_list')

    return render(request, 'maintenance/maintenance_form.html', {
        'form': form
    })


@maintenance_manager_required
@require_POST
def update_maintenance_status(request, record_id):
    requested_status = request.POST.get('status')

    if requested_status not in ['IN_PROGRESS', 'RESOLVED']:
        messages.error(request, 'Invalid maintenance status.')
        return redirect('maintenance_list')

    with transaction.atomic():
        initial_record = get_object_or_404(
            MaintenanceRecord.objects.only('resource_id'),
            pk=record_id
        )

        resource = Resource.objects.select_for_update().get(
            pk=initial_record.resource_id
        )

        record = get_object_or_404(
            MaintenanceRecord.objects.select_for_update(),
            pk=record_id
        )

        if record.status == 'RESOLVED':
            messages.error(
                request,
                'This maintenance record has already been resolved.'
            )

        elif requested_status == 'IN_PROGRESS':
            if record.status != 'REPORTED':
                messages.error(
                    request,
                    'Only reported issues can be marked as in progress.'
                )
            else:
                record.status = 'IN_PROGRESS'
                record.save(update_fields=['status'])

                messages.success(
                    request,
                    'Maintenance marked as in progress.'
                )

        elif requested_status == 'RESOLVED':
            record.status = 'RESOLVED'
            record.resolved_at = timezone.now()
            record.save(update_fields=['status', 'resolved_at'])

            other_open_records = MaintenanceRecord.objects.filter(
                resource=resource,
                status__in=['REPORTED', 'IN_PROGRESS']
            ).exclude(pk=record.pk)

            if not other_open_records.exists():
                resource.status = 'AVAILABLE'
                resource.save(update_fields=['status'])

            messages.success(
                request,
                'Maintenance issue resolved successfully.'
            )

    return redirect('maintenance_list')
