from django.contrib import admin

from .models import Council, Evaluation, EvaluationDetail


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'tenant', 'evaluated_at', 'status', 'average_score')
    list_filter = ('tenant', 'status')


@admin.register(Council)
class CouncilAdmin(admin.ModelAdmin):
    list_display = ('evaluation', 'examiner', 'tenant')
    list_filter = ('tenant',)


@admin.register(EvaluationDetail)
class EvaluationDetailAdmin(admin.ModelAdmin):
    list_display = ('evaluation', 'council', 'criterion', 'score', 'tenant')
    list_filter = ('tenant', 'criterion')
