from django.contrib import admin

from .models import Commission, KpiParticipant, KpiSession


@admin.register(KpiSession)
class KpiSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'session_date', 'trainer', 'status')
    list_filter = ('tenant', 'status')


@admin.register(KpiParticipant)
class KpiParticipantAdmin(admin.ModelAdmin):
    list_display = ('session', 'employee', 'score', 'result', 'tenant')
    list_filter = ('tenant',)


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('trainer', 'period', 'amount', 'status', 'tenant')
    list_filter = ('tenant', 'status')
