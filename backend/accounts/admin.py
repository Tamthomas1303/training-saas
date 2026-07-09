from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Tenant, User


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'plan', 'status', 'created_at')
    search_fields = ('name',)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'full_name', 'role', 'tenant', 'status', 'is_active')
    list_filter = ('role', 'tenant', 'status')
    fieldsets = UserAdmin.fieldsets + (
        (
            'Thông tin SaaS',
            {
                'fields': (
                    'tenant',
                    'full_name',
                    'role',
                    'job_title',
                    'trainer_zone',
                    'google_email',
                    'status',
                )
            },
        ),
    )
