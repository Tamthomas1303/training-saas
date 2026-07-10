from django.contrib import admin

from .models import CourseResult, ExamResult


@admin.register(CourseResult)
class CourseResultAdmin(admin.ModelAdmin):
    list_display = ('employee', 'course_name', 'score', 'status', 'tenant', 'synced_at')
    list_filter = ('tenant', 'status')


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_display = ('employee', 'exam_name', 'attempt', 'score', 'passed', 'tenant', 'synced_at')
    list_filter = ('tenant', 'passed')
