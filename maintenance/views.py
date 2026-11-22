
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction

from .models import MaintenanceRecord
from .forms import MaintenanceRecordForm
from resources.models import Resource


def can_manage_maintenance(user):
    return user.is_superuser or (
        hasattr(user, 'profile') and
        user.profile.role in ['STAFF', 'ADMIN']
    )


@login_required
@user_passes_test(can_manage_maintenance)
def maintenance_list(request):
    records = MaintenanceRecord.objects.select_related(
        'resource', 'reported_by'
    ).all()

    return render(request, 'maintenance/maintenance_list.html', {
        'records': records
    })


@login_required
@user_passes_test(can_manage_maintenance)
def report_maintenance(request):
    form = MaintenanceRecordForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = form.save(commit=False)
            record.reported_by = request.user
            record.save()

            resource = record.resource
            resource.status = 'MAINTENANCE'
            resource.save(update_fields=['status'])

        messages.success(request, 'Maintenance issue reported successfully.')
        return redirect('maintenance_list')

    return render(request, 'maintenance/maintenance_form.html', {
        'form': form
    })


@login_required
@user_passes_test(can_manage_maintenance)
def update_maintenance_status(request, record_id):
    record = get_object_or_404(MaintenanceRecord, pk=record_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')

        if new_status in ['IN_PROGRESS', 'RESOLVED']:
            with transaction.atomic():
                record.status = new_status

                if new_status == 'RESOLVED':
                    from django.utils import timezone
                    record.resolved_at = timezone.now()

                    resource = record.resource
                    resource.status = 'AVAILABLE'
                    resource.save(update_fields=['status'])

                record.save()

            messages.success(request, 'Maintenance status updated.')

    return redirect('maintenance_list')
