from django.contrib import admin
from .models import MaintenanceRecord

@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ('resource', 'reported_by', 'status', 'reported_at', 'resolved_at')
    list_filter = ('status', 'reported_at')
    search_fields = ('resource__name', 'issue_description')
    readonly_fields = ('reported_at',)