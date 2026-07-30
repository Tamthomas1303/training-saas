from django.contrib import admin

from .models import CourseResult, ExamResult, ExamScoreAdjustment


@admin.register(CourseResult)
class CourseResultAdmin(admin.ModelAdmin):
    list_display = ('employee', 'course_name', 'score', 'status', 'tenant', 'synced_at')
    list_filter = ('tenant', 'status')


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'exam_name', 'attempt', 'score', 'score_adjusted', 'passed', 'tenant', 'synced_at',
    )
    list_filter = ('tenant', 'passed')


@admin.register(ExamScoreAdjustment)
class ExamScoreAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('exam_result', 'old_score', 'new_score', 'adjusted_by', 'tenant', 'created_at')
    list_filter = ('tenant',)
    readonly_fields = ('exam_result', 'old_score', 'new_score', 'reason', 'adjusted_by', 'tenant', 'created_at')
