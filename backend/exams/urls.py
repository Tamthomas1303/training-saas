from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AnswerSaveView,
    AssessmentAssignmentViewSet,
    AssessmentAssignView,
    AssessmentQuestionViewSet,
    AssessmentResultsExportView,
    AssessmentResultsView,
    AssessmentViewSet,
    AttemptDetailView,
    ExamSessionTrackingExportView,
    ExamSessionTrackingView,
    ExamSessionViewSet,
    GradeAttemptView,
    GradingListView,
    MyAssessmentsView,
    QuestionBankViewSet,
    QuestionExportCompetencyView,
    QuestionImportCompetencyView,
    QuestionViewSet,
    ReorderView,
    StartAttemptView,
    SubmitAttemptView,
)

router = DefaultRouter()
router.register('banks', QuestionBankViewSet, basename='exam-bank')
router.register('questions', QuestionViewSet, basename='exam-question')
router.register('assessment-questions', AssessmentQuestionViewSet, basename='exam-assessment-question')
router.register('assignments', AssessmentAssignmentViewSet, basename='exam-assignment')
router.register('assessments', AssessmentViewSet, basename='exam-assessment')
router.register('sessions', ExamSessionViewSet, basename='exam-session')

urlpatterns = [
    path('my/', MyAssessmentsView.as_view(), name='exam-my'),
    path('my/<int:assessment_id>/start/', StartAttemptView.as_view(), name='exam-start'),
    path('attempts/<int:pk>/', AttemptDetailView.as_view(), name='exam-attempt-detail'),
    path('attempts/<int:pk>/answer/', AnswerSaveView.as_view(), name='exam-attempt-answer'),
    path('attempts/<int:pk>/submit/', SubmitAttemptView.as_view(), name='exam-attempt-submit'),
    path('attempts/<int:pk>/grade/', GradeAttemptView.as_view(), name='exam-attempt-grade'),
    path('grading/', GradingListView.as_view(), name='exam-grading'),
    path(
        'questions/export-competency/', QuestionExportCompetencyView.as_view(),
        name='exam-question-export-competency',
    ),
    path(
        'questions/import-competency/', QuestionImportCompetencyView.as_view(),
        name='exam-question-import-competency',
    ),
    path('reorder/', ReorderView.as_view(), name='exam-reorder'),
    path('assessments/<int:pk>/assign/', AssessmentAssignView.as_view(), name='exam-assessment-assign'),
    path('assessments/<int:pk>/results/', AssessmentResultsView.as_view(), name='exam-assessment-results'),
    path(
        'assessments/<int:pk>/results/export/', AssessmentResultsExportView.as_view(),
        name='exam-assessment-results-export',
    ),
    path('sessions/<int:pk>/tracking/', ExamSessionTrackingView.as_view(), name='exam-session-tracking'),
    path(
        'sessions/<int:pk>/tracking/export/', ExamSessionTrackingExportView.as_view(),
        name='exam-session-tracking-export',
    ),
] + router.urls
