from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardStatsView,
    EmployeeViewSet,
    EvaluationHistoryImportView,
    ExamBatchListView,
    ExamHistoryImportView,
    HrSyncHistoryView,
    HrSyncRosterView,
    HrSyncSourceView,
    MgmtDevelopmentListView,
    HomeStatsView,
    LevelUpCompleteView,
    LevelUpEligibleView,
    LevelUpEnrollmentListView,
    LevelUpEvaluateView,
    LevelUpFailView,
    LevelUpOpenTrainingView,
    LevelUpOptionsView,
    LevelUpRegisterView,
    LevelUpRoundView,
    TalentCandidateListView,
    TalentPoolListView,
    TalentReviewView,
    PositionListView,
    StudentOfficeResultView,
    RecruitmentImportFileView,
    RecruitmentSourceView,
    RecruitmentSyncNowView,
    StudentChangeStatusView,
    StudentDetailView,
    StudentExportProbationResultView,
)

router = DefaultRouter()
router.register('', EmployeeViewSet, basename='employee')

urlpatterns = [
    path('positions/', PositionListView.as_view(), name='employee-positions'),
    path('recruitment-source/', RecruitmentSourceView.as_view(), name='recruitment-source'),
    path('sync-now/', RecruitmentSyncNowView.as_view(), name='recruitment-sync-now'),
    path('hr-sync-sources/', HrSyncSourceView.as_view(), name='hr-sync-sources'),
    path('hr-sync-roster/', HrSyncRosterView.as_view(), name='hr-sync-roster'),
    path('hr-sync-history/', HrSyncHistoryView.as_view(), name='hr-sync-history'),
    path('mgmt-development/', MgmtDevelopmentListView.as_view(), name='mgmt-development'),
    path('import-file/', RecruitmentImportFileView.as_view(), name='recruitment-import-file'),
    path('import-exam-history/', ExamHistoryImportView.as_view(), name='import-exam-history'),
    path('import-eval-history/', EvaluationHistoryImportView.as_view(), name='import-eval-history'),
    path('dashboard/', DashboardStatsView.as_view(), name='employee-dashboard'),
    path('home/', HomeStatsView.as_view(), name='employee-home'),
    path('<int:pk>/detail/', StudentDetailView.as_view(), name='employee-detail'),
    path('<int:pk>/change-status/', StudentChangeStatusView.as_view(), name='employee-change-status'),
    path('<int:pk>/office-result/', StudentOfficeResultView.as_view(), name='employee-office-result'),
    path('levelup-eligible/', LevelUpEligibleView.as_view(), name='employee-levelup-eligible'),
    path('<int:pk>/levelup-options/', LevelUpOptionsView.as_view(), name='employee-levelup-options'),
    path('<int:pk>/levelup-register/', LevelUpRegisterView.as_view(), name='employee-levelup-register'),
    path('exam-batches/', ExamBatchListView.as_view(), name='employee-exam-batches'),
    path('levelup-enrollments/', LevelUpEnrollmentListView.as_view(), name='employee-levelup-enrollments'),
    path(
        'levelup-enrollments/<int:pk>/open-training/', LevelUpOpenTrainingView.as_view(),
        name='employee-levelup-open-training',
    ),
    path(
        'levelup-enrollments/<int:pk>/round/', LevelUpRoundView.as_view(),
        name='employee-levelup-round',
    ),
    path(
        'levelup-enrollments/<int:pk>/evaluate/', LevelUpEvaluateView.as_view(),
        name='employee-levelup-evaluate',
    ),
    path(
        'levelup-enrollments/<int:pk>/complete/', LevelUpCompleteView.as_view(),
        name='employee-levelup-complete',
    ),
    path(
        'levelup-enrollments/<int:pk>/fail/', LevelUpFailView.as_view(),
        name='employee-levelup-fail',
    ),
    path('talent-pool/', TalentPoolListView.as_view(), name='employee-talent-pool'),
    path('talent-candidates/', TalentCandidateListView.as_view(), name='employee-talent-candidates'),
    path('<int:pk>/talent-review/', TalentReviewView.as_view(), name='employee-talent-review'),
    path(
        '<int:pk>/export-probation-result/', StudentExportProbationResultView.as_view(),
        name='employee-export-probation-result',
    ),
] + router.urls
