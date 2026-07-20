from django.urls import path

from .council_views import (
    CouncilAddMemberView,
    CouncilCreateView,
    CouncilDetailView,
    CouncilFinalizeOView,
    CouncilMemberFormView,
    CouncilSubmitView,
    GuestFormView,
    GuestSubmitView,
    ShiftOpsFormView,
    ShiftOpsSaveView,
)
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
    # Hội đồng cấp O (Phase 2)
    path('shiftops/', ShiftOpsFormView.as_view(), name='shiftops-form'),
    path('shiftops/save/', ShiftOpsSaveView.as_view(), name='shiftops-save'),
    path('council-o/create/', CouncilCreateView.as_view(), name='council-o-create'),
    path('council-o/add-member/', CouncilAddMemberView.as_view(), name='council-o-add-member'),
    path('council-o/member-form/', CouncilMemberFormView.as_view(), name='council-o-member-form'),
    path('council-o/submit/', CouncilSubmitView.as_view(), name='council-o-submit'),
    path('council-o/finalize/', CouncilFinalizeOView.as_view(), name='council-o-finalize'),
    path('council-o/', CouncilDetailView.as_view(), name='council-o-detail'),
    path('council-guest/<str:token>/submit/', GuestSubmitView.as_view(), name='council-guest-submit'),
    path('council-guest/<str:token>/', GuestFormView.as_view(), name='council-guest-form'),
]
