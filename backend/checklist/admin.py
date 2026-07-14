from django.contrib import admin

from .models import Checklist, Document, TrainingProgress


@admin.register(Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'brand', 'position', 'day', 'category', 'tenant', 'order')
    list_filter = ('tenant', 'brand', 'position', 'level_group')
    search_fields = ('task_name',)


@admin.register(TrainingProgress)
class TrainingProgressAdmin(admin.ModelAdmin):
    list_display = ('employee', 'checklist', 'trainer', 'status', 'completed_at')
    list_filter = ('tenant', 'status')


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'position', 'status', 'tenant', 'uploaded_at')
    list_filter = ('tenant', 'brand', 'position', 'status')
