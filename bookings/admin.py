from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('user', 'resource', 'start_datetime', 'end_datetime', 'status')
    list_filter = ('status', 'start_datetime')
    search_fields = ('user__username', 'resource__name')
    readonly_fields = ('created_at',)