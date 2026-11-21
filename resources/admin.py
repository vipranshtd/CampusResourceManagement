from django.contrib import admin
from .models import Category, Location, Resource

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'building', 'floor')
    search_fields = ('name', 'building')

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'asset_tag', 'category', 'location', 'status', 'condition')
    list_filter = ('category', 'location', 'status', 'condition')
    search_fields = ('name', 'asset_tag')