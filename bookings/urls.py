
from django.urls import path
from . import views

urlpatterns = [
    path('catalog/', views.resource_catalog, name='resource_catalog'),
    path('create/', views.create_booking, name='create_booking'),
    path('create/<int:resource_id>/', views.create_booking, name='create_booking_for_resource'),
    path('availability/', views.check_booking_availability, name='check_booking_availability'),
    path('my/', views.my_bookings, name='my_bookings'),
    path('cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('manage/', views.manage_bookings, name='manage_bookings'),
    path('status/<int:booking_id>/', views.update_booking_status, name='update_booking_status'),
]
