from django.urls import path

from .views import (
    CouncilFinalizeView,
    CouncilSaveView,
    CouncilSummaryView,
    EvaluationCriteriaView,
    EvaluationDraftView,
    EvaluationSaveView,
)

urlpatterns = [
    path('criteria/', EvaluationCriteriaView.as_view(), name='evaluation-criteria'),
    path('draft/', EvaluationDraftView.as_view(), name='evaluation-draft'),
    path('save/', EvaluationSaveView.as_view(), name='evaluation-save'),
    path('council/save/', CouncilSaveView.as_view(), name='council-save'),
    path('council/finalize/', CouncilFinalizeView.as_view(), name='council-finalize'),
    path('council/', CouncilSummaryView.as_view(), name='council-summary'),
]
