from django.contrib import admin

from .models import Commission, KpiParticipant, KpiSession


@admin.register(KpiSession)
class KpiSessionAdmin(admin.ModelAdmin):
    list_display = ('topic', 'restaurant', 'trainer', 'date', 'tenant')
    list_filter = ('tenant', 'restaurant')


@admin.register(KpiParticipant)
class KpiParticipantAdmin(admin.ModelAdmin):
    list_display = ('session', 'employee', 'tenant')
    list_filter = ('tenant',)


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'trainer', 'amount', 'status', 'month', 'year', 'tenant')
    list_filter = ('tenant', 'status')
