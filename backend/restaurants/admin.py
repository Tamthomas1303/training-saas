from django.contrib import admin

from .models import Restaurant


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'brand', 'tenant', 'status')
    list_filter = ('tenant', 'brand', 'status')
    search_fields = ('code', 'name')
