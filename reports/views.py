
import csv
from io import BytesIO

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.utils import timezone

from bookings.models import Booking
from resources.models import Resource
from maintenance.models import MaintenanceRecord

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4


def can_view_reports(user):
    return user.is_superuser or (
        hasattr(user, 'profile') and
        user.profile.role in ['STAFF', 'ADMIN']
    )


@login_required
@user_passes_test(can_view_reports)
def reports_dashboard(request):
    context = {
        'total_resources': Resource.objects.count(),
        'available_resources': Resource.objects.filter(status='AVAILABLE').count(),
        'maintenance_resources': Resource.objects.filter(status='MAINTENANCE').count(),
        'total_bookings': Booking.objects.count(),
        'pending_bookings': Booking.objects.filter(status='PENDING').count(),
        'approved_bookings': Booking.objects.filter(status='APPROVED').count(),
        'total_maintenance': MaintenanceRecord.objects.count(),
        'open_maintenance': MaintenanceRecord.objects.exclude(status='RESOLVED').count(),
    }

    return render(request, 'reports/dashboard.html', context)


@login_required
@user_passes_test(can_view_reports)
def export_bookings_csv(request):
    bookings = Booking.objects.select_related(
        'user', 'resource'
    ).all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="booking_report.csv"'

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


@login_required
@user_passes_test(can_view_reports)
def export_summary_pdf(request):
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4
    )

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
    response['Content-Disposition'] = 'attachment; filename="campus_resource_report.pdf"'
    response.write(pdf)

    return response
