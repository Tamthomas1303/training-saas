from django.contrib import admin

from .models import Evaluation, EvaluationCriteria, EvaluationDetail


@admin.register(EvaluationCriteria)
class EvaluationCriteriaAdmin(admin.ModelAdmin):
    list_display = ('content', 'brand', 'position', 'eval_type', 'max_score', 'is_mandatory', 'require_photo', 'tenant')
    list_filter = ('tenant', 'brand', 'eval_type', 'is_mandatory', 'require_photo')


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'evaluator', 'eval_type', 'status', 'result', 'percent', 'tenant')
    list_filter = ('tenant', 'eval_type', 'status', 'result')


@admin.register(EvaluationDetail)
class EvaluationDetailAdmin(admin.ModelAdmin):
    list_display = ('evaluation', 'criteria_id', 'content', 'score', 'max_score', 'tenant')
    list_filter = ('tenant',)
