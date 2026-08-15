from django.contrib import admin

from .models import CompetencyGroup, Competency, DashboardIndicator, PositionGroupWeight, PositionTarget


@admin.register(CompetencyGroup)
class CompetencyGroupAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'order', 'tenant')
    list_filter = ('tenant',)


@admin.register(Competency)
class CompetencyAdmin(admin.ModelAdmin):
    list_display = ('name', 'group', 'order', 'tenant')
    list_filter = ('tenant', 'group')


@admin.register(PositionTarget)
class PositionTargetAdmin(admin.ModelAdmin):
    list_display = ('position', 'competency', 'target_score', 'tenant')
    list_filter = ('tenant',)


@admin.register(PositionGroupWeight)
class PositionGroupWeightAdmin(admin.ModelAdmin):
    list_display = ('position', 'group', 'weight', 'tenant')
    list_filter = ('tenant', 'group')


@admin.register(DashboardIndicator)
class DashboardIndicatorAdmin(admin.ModelAdmin):
    list_display = ('key', 'label', 'enabled', 'direction', 'order', 'tenant')
    list_filter = ('tenant', 'enabled', 'direction')
