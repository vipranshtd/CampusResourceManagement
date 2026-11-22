
from django.urls import path
from . import views

urlpatterns = [
    path('', views.reports_dashboard, name='reports_dashboard'),
    path('export/csv/', views.export_bookings_csv, name='export_bookings_csv'),
    path('export/pdf/', views.export_summary_pdf, name='export_summary_pdf'),
]
