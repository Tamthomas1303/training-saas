from django.contrib import admin

from .models import (
    ClsExamCompetencyMap,
    CompetencyGroup,
    Competency,
    CompetencyScoringConfig,
    DashboardIndicator,
    PositionGroupWeight,
    PositionTarget,
)


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


@admin.register(ClsExamCompetencyMap)
class ClsExamCompetencyMapAdmin(admin.ModelAdmin):
    list_display = ('exam_name', 'competency', 'tenant')
    list_filter = ('tenant',)


@admin.register(CompetencyScoringConfig)
class CompetencyScoringConfigAdmin(admin.ModelAdmin):
    list_display = ('tenant', 'theory_weight', 'practice_weight')
