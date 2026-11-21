from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'department', 'phone', 'enrollment_number')
    list_filter = ('role', 'department')
    search_fields = ('user__username', 'user__email', 'enrollment_number')