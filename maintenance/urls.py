
from django.urls import path
from . import views

urlpatterns = [
    path('', views.maintenance_list, name='maintenance_list'),
    path('report/', views.report_maintenance, name='report_maintenance'),
    path('update/<int:record_id>/', views.update_maintenance_status, name='update_maintenance_status'),
]
