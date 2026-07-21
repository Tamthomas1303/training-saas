from django.urls import path
from rest_framework.routers import DefaultRouter

from .council_views import (
    CouncilCriteriaViewSet,
    CriteriaImportView,
    CouncilAddMemberView,
    CouncilCreateView,
    CouncilDetailView,
    CouncilFinalizeOView,
    CouncilMemberFormView,
    CouncilPdfView,
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
    path('council-o/pdf/', CouncilPdfView.as_view(), name='council-o-pdf'),
    path('council-o/', CouncilDetailView.as_view(), name='council-o-detail'),
    path('council-guest/<str:token>/submit/', GuestSubmitView.as_view(), name='council-guest-submit'),
    path('council-guest/<str:token>/', GuestFormView.as_view(), name='council-guest-form'),
    # Nhập bộ tiêu chí từ file (phải khai báo TRƯỚC router để 'import-file' không bị hiểu là pk)
    path('council-criteria/import-file/', CriteriaImportView.as_view(), name='criteria-import'),
]

router = DefaultRouter()
router.register('council-criteria', CouncilCriteriaViewSet, basename='council-criteria')
urlpatterns += router.urls
