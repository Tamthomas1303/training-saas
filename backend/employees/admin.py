from django.contrib import admin

from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'position', 'tenant', 'restaurant', 'employee_status')
    list_filter = ('tenant', 'employee_status', 'operation_unit')
    search_fields = ('code', 'name')
