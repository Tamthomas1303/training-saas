from django.contrib import admin

from .models import Course, CourseModule, Enrollment, Lesson, LessonProgress, ScormPackage, ScormTracking


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'tenant', 'created_by', 'created_at')
    list_filter = ('tenant', 'status')


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'tenant')
    list_filter = ('tenant',)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'type', 'complete_rule', 'order', 'tenant')
    list_filter = ('tenant', 'type', 'complete_rule')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'course', 'status', 'source', 'tenant')
    list_filter = ('tenant', 'status', 'source')


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'lesson', 'status', 'watched_pct', 'tenant')
    list_filter = ('tenant', 'status')


@admin.register(ScormPackage)
class ScormPackageAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'version', 'title', 'tenant')
    list_filter = ('tenant', 'version')


@admin.register(ScormTracking)
class ScormTrackingAdmin(admin.ModelAdmin):
    list_display = ('lesson_progress', 'lesson_status', 'score_raw', 'updated_at', 'tenant')
    list_filter = ('tenant', 'lesson_status')
