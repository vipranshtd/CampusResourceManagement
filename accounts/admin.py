
from django.contrib import admin
from django.contrib.auth.models import User, Group, Permission
from django.contrib.auth.admin import UserAdmin

from .models import Profile


ADMIN_MODEL_PERMISSIONS = {
    'auth': {
        'user': ['view', 'add', 'change', 'delete'],
    },
    'accounts': {
        'profile': ['view', 'add', 'change', 'delete'],
    },
    'resources': {
        'resource': ['view', 'add', 'change', 'delete'],
        'category': ['view', 'add', 'change', 'delete'],
        'location': ['view', 'add', 'change', 'delete'],
    },
    'bookings': {
        'booking': ['view', 'add', 'change', 'delete'],
    },
    'maintenance': {
        'maintenancerecord': ['view', 'add', 'change', 'delete'],
    },
}


def sync_administrator_access(user):
    profile = getattr(user, 'profile', None)

    is_administrator = (
        profile is not None and profile.role == 'ADMIN'
    )

    group, created = Group.objects.get_or_create(
        name='Campus Administrators'
    )

    permissions = []

    for app_label, models in ADMIN_MODEL_PERMISSIONS.items():
        for model_name, actions in models.items():
            for action in actions:
                codename = f'{action}_{model_name}'

                permission = Permission.objects.filter(
                    content_type__app_label=app_label,
                    content_type__model=model_name,
                    codename=codename
                ).first()

                if permission:
                    permissions.append(permission)

    group.permissions.set(permissions)

    if is_administrator:
        user.groups.add(group)
    else:
        user.groups.remove(group)

    should_have_staff_access = (
        is_administrator or user.is_superuser
    )

    if user.is_staff != should_have_staff_access:
        user.is_staff = should_have_staff_access
        user.save(update_fields=['is_staff'])


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 1
    max_num = 1


class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]

    fieldsets = (
        (None, {
            'fields': ('username', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email')
        }),
        ('Access', {
            'fields': ('is_active', 'is_staff')
        }),
        ('Important Dates', {
            'fields': ('last_login', 'date_joined')
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'password1',
                'password2',
                'first_name',
                'last_name',
                'email',
            ),
        }),
    )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        sync_administrator_access(form.instance)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):

    list_display = (
        'user',
        'role',
        'institutional_id',
        'department',
        'phone',
    )

    list_filter = ('role', 'department')

    search_fields = (
        'user__username',
        'user__email',
        'institutional_id',
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        sync_administrator_access(obj.user)
