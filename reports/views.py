
import csv
from io import BytesIO
from functools import wraps

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.utils import timezone

from bookings.models import Booking
from resources.models import Resource
from maintenance.models import MaintenanceRecord

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4


def can_view_reports(user):
    return user.is_superuser or (
        hasattr(user, 'profile') and
        user.profile.role == 'ADMIN'
    )


def administrator_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_view_reports(request.user):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper


@administrator_required
def reports_dashboard(request):
    total_resources = Resource.objects.count()
    total_bookings = Booking.objects.count()
    total_maintenance = MaintenanceRecord.objects.count()

    available_resources = Resource.objects.filter(status='AVAILABLE').count()
    unavailable_resources = Resource.objects.filter(status='UNAVAILABLE').count()
    maintenance_resources = Resource.objects.filter(status='MAINTENANCE').count()

    pending_bookings = Booking.objects.filter(status='PENDING').count()
    approved_bookings = Booking.objects.filter(status='APPROVED').count()
    rejected_bookings = Booking.objects.filter(status='REJECTED').count()
    issued_bookings = Booking.objects.filter(status='ISSUED').count()
    returned_bookings = Booking.objects.filter(status='RETURNED').count()
    cancelled_bookings = Booking.objects.filter(status='CANCELLED').count()

    reported_maintenance = MaintenanceRecord.objects.filter(status='REPORTED').count()
    in_progress_maintenance = MaintenanceRecord.objects.filter(status='IN_PROGRESS').count()
    resolved_maintenance = MaintenanceRecord.objects.filter(status='RESOLVED').count()

    def percentage(count, total):
        return round((count / total) * 100, 1) if total else 0

    resource_status_data = [
        {
            'name': 'Available',
            'count': available_resources,
            'percentage': percentage(available_resources, total_resources),
            'color': 'success'
        },
        {
            'name': 'Unavailable',
            'count': unavailable_resources,
            'percentage': percentage(unavailable_resources, total_resources),
            'color': 'secondary'
        },
        {
            'name': 'Under Maintenance',
            'count': maintenance_resources,
            'percentage': percentage(maintenance_resources, total_resources),
            'color': 'danger'
        },
    ]

    booking_status_data = [
        {
            'name': 'Pending',
            'count': pending_bookings,
            'percentage': percentage(pending_bookings, total_bookings),
            'color': 'warning'
        },
        {
            'name': 'Approved',
            'count': approved_bookings,
            'percentage': percentage(approved_bookings, total_bookings),
            'color': 'primary'
        },
        {
            'name': 'Rejected',
            'count': rejected_bookings,
            'percentage': percentage(rejected_bookings, total_bookings),
            'color': 'danger'
        },
        {
            'name': 'Issued',
            'count': issued_bookings,
            'percentage': percentage(issued_bookings, total_bookings),
            'color': 'info'
        },
        {
            'name': 'Returned',
            'count': returned_bookings,
            'percentage': percentage(returned_bookings, total_bookings),
            'color': 'success'
        },
        {
            'name': 'Cancelled',
            'count': cancelled_bookings,
            'percentage': percentage(cancelled_bookings, total_bookings),
            'color': 'secondary'
        },
    ]

    maintenance_status_data = [
        {
            'name': 'Reported',
            'count': reported_maintenance,
            'percentage': percentage(reported_maintenance, total_maintenance),
            'color': 'warning'
        },
        {
            'name': 'In Progress',
            'count': in_progress_maintenance,
            'percentage': percentage(in_progress_maintenance, total_maintenance),
            'color': 'primary'
        },
        {
            'name': 'Resolved',
            'count': resolved_maintenance,
            'percentage': percentage(resolved_maintenance, total_maintenance),
            'color': 'success'
        },
    ]

    context = {
        'total_resources': total_resources,
        'available_resources': available_resources,
        'unavailable_resources': unavailable_resources,
        'maintenance_resources': maintenance_resources,

        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'approved_bookings': approved_bookings,
        'rejected_bookings': rejected_bookings,
        'issued_bookings': issued_bookings,
        'returned_bookings': returned_bookings,
        'cancelled_bookings': cancelled_bookings,

        'total_maintenance': total_maintenance,
        'open_maintenance': reported_maintenance + in_progress_maintenance,
        'reported_maintenance': reported_maintenance,
        'in_progress_maintenance': in_progress_maintenance,
        'resolved_maintenance': resolved_maintenance,

        'resource_status_data': resource_status_data,
        'booking_status_data': booking_status_data,
        'maintenance_status_data': maintenance_status_data,
    }

    return render(request, 'reports/dashboard.html', context)



@administrator_required
def export_bookings_csv(request):
    bookings = Booking.objects.select_related(
        'user', 'resource'
    ).all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (
        'attachment; filename="booking_report.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        'Username',
        'Resource',
        'Start Date',
        'End Date',
        'Purpose',
        'Status'
    ])

    for booking in bookings:
        writer.writerow([
            booking.user.username,
            booking.resource.name,
            booking.start_datetime,
            booking.end_datetime,
            booking.purpose,
            booking.get_status_display()
        ])

    return response


@administrator_required
def export_summary_pdf(request):
    buffer = BytesIO()

    document = SimpleDocTemplate(buffer, pagesize=A4)

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(
        "Campus Resource Management Report",
        styles['Title']
    ))

    elements.append(Spacer(1, 20))

    elements.append(Paragraph(
        f"Generated on: {timezone.localtime().strftime('%d-%m-%Y %H:%M')}",
        styles['Normal']
    ))

    elements.append(Spacer(1, 20))

    data = [
        ['Metric', 'Count'],
        ['Total Resources', Resource.objects.count()],
        ['Available Resources', Resource.objects.filter(status='AVAILABLE').count()],
        ['Resources Under Maintenance', Resource.objects.filter(status='MAINTENANCE').count()],
        ['Total Bookings', Booking.objects.count()],
        ['Pending Bookings', Booking.objects.filter(status='PENDING').count()],
        ['Approved Bookings', Booking.objects.filter(status='APPROVED').count()],
        ['Total Maintenance Records', MaintenanceRecord.objects.count()],
        ['Open Maintenance Records', MaintenanceRecord.objects.exclude(status='RESOLVED').count()],
    ]

    table = Table(data, colWidths=[300, 150])

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
    ]))

    elements.append(table)
    document.build(elements)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        'attachment; filename="campus_resource_report.pdf"'
    )
    response.write(pdf)

    return response
