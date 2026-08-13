from django.contrib import admin

from .models import (
    Answer,
    Assessment,
    AssessmentAssignment,
    AssessmentQuestion,
    Attempt,
    Question,
    QuestionBank,
    QuestionOption,
)


@admin.register(QuestionBank)
class QuestionBankAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'tenant')
    list_filter = ('tenant',)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('bank', 'type', 'difficulty', 'points', 'tenant')
    list_filter = ('tenant', 'type', 'difficulty')


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    list_display = ('question', 'order', 'is_correct', 'tenant')
    list_filter = ('tenant',)


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'pass_mark', 'max_attempts', 'tenant')
    list_filter = ('tenant', 'status')


@admin.register(AssessmentQuestion)
class AssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ('assessment', 'question', 'order', 'tenant')
    list_filter = ('tenant',)


@admin.register(AssessmentAssignment)
class AssessmentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('employee', 'assessment', 'status', 'tenant')
    list_filter = ('tenant', 'status')


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ('employee', 'assessment', 'attempt_no', 'status', 'percent', 'passed', 'tenant')
    list_filter = ('tenant', 'status', 'passed')


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'question', 'is_correct', 'auto_score', 'manual_score', 'tenant')
    list_filter = ('tenant', 'is_correct')
