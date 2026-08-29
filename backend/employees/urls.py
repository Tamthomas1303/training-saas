from django.urls import path
from rest_framework.routers import DefaultRouter, SimpleRouter

from .views import (
    AutomationSettingsView,
    CompetencyGapView,
    DashboardStatsView,
    EmployeeCreateLoginView,
    EmployeeViewSet,
    EvaluationHistoryImportView,
    ExamBatchListView,
    ExamHistoryImportView,
    HrSyncHistoryView,
    HrSyncRosterView,
    HrSyncSourceView,
    MgmtDevelopmentListView,
    HomeStatsView,
    OnboardingCourseRuleViewSet,
    LevelUpCompleteView,
    LevelUpEligibleView,
    LevelUpEnrollmentListView,
    LevelUpEvaluateView,
    LevelUpFailView,
    LevelUpOpenTrainingView,
    LevelUpOptionsView,
    LevelUpRegisterView,
    LevelUpRoundView,
    ProbationExamCandidateApproveView,
    ProbationExamCandidateListView,
    ProbationExamCandidateRejectView,
    ProbationExamRuleViewSet,
    TalentCandidateListView,
    TalentPoolListView,
    TalentReviewView,
    PositionListView,
    PositionViewSet,
    StudentOfficeResultView,
    RecruitmentImportFileView,
    RecruitmentSourceView,
    RecruitmentSyncNowView,
    StudentChangeStatusView,
    StudentDetailView,
    StudentExamRegradeView,
    StudentExamResultsView,
    StudentExportProbationResultView,
    StudentRecomputeFinalResultView,
)

router = DefaultRouter()
router.register('', EmployeeViewSet, basename='employee')

# Router rieng, DAT TRUOC router cua EmployeeViewSet (prefix '') trong urlpatterns - tranh bi
# pattern '^(?P<pk>[^/.]+)/$' cua EmployeeViewSet (prefix rong) nuot mat cac path co 1 doan nhu
# 'onboarding-course-rules/' neu no dung SAU trong danh sach urlpatterns.
#
# QUAN TRONG (Prompt_Fix_TrangTrang_MapUndefined.md - da gay trang man /employees): PHAI dung
# SimpleRouter, KHONG dung DefaultRouter o day. DefaultRouter tu sinh THEM 1 "API root view" rieng
# tai chinh pattern '^$' (rong) cho MOI instance router - vi automation_router.urls dung TRUOC
# router.urls trong urlpatterns, root view rong cua automation_router (chi liet ke
# onboarding-course-rules/probation-exam-rules) se KHOP TRUOC va NUOT MAT list-view that su cua
# EmployeeViewSet (cung o pattern '^$' do router.register('', ...) - prefix rong). Hau qua:
# GET /api/employees/ tra ve JSON {"onboarding-course-rules": "...", "probation-exam-rules": "..."}
# thay vi {count, results} phan trang -> frontend goi data.results.map() tren undefined -> trang
# man /employees. SimpleRouter KHONG sinh root view nen khong con xung dot.
automation_router = SimpleRouter()
automation_router.register(
    'onboarding-course-rules', OnboardingCourseRuleViewSet, basename='onboarding-course-rule',
)
automation_router.register(
    'probation-exam-rules', ProbationExamRuleViewSet, basename='probation-exam-rule',
)
# Muc 16 Phase 1 phan A - CRUD danh muc Vi tri chuc danh. Prefix 'positions-catalog' (KHAC
# 'positions/' o duoi - PositionListView, endpoint doc-only gop chuoi goi y da dung tu truoc,
# giu nguyen contract cu cho 5 noi frontend dang goi) de tranh dam path.
automation_router.register('positions-catalog', PositionViewSet, basename='position')

urlpatterns = [
    path('automation-settings/', AutomationSettingsView.as_view(), name='automation-settings'),
    path(
        'probation-exam-candidates/', ProbationExamCandidateListView.as_view(),
        name='probation-exam-candidate-list',
    ),
    path(
        'probation-exam-candidates/<int:pk>/approve/', ProbationExamCandidateApproveView.as_view(),
        name='probation-exam-candidate-approve',
    ),
    path(
        'probation-exam-candidates/<int:pk>/reject/', ProbationExamCandidateRejectView.as_view(),
        name='probation-exam-candidate-reject',
    ),
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
    path('<int:pk>/detail/', StudentDetailView.as_view(), name='employee-student-detail'),
    path('<int:pk>/change-status/', StudentChangeStatusView.as_view(), name='employee-change-status'),
    path('<int:pk>/office-result/', StudentOfficeResultView.as_view(), name='employee-office-result'),
    path('<int:pk>/exam-results/', StudentExamResultsView.as_view(), name='employee-exam-results'),
    path('<int:pk>/exam-regrade/', StudentExamRegradeView.as_view(), name='employee-exam-regrade'),
    path(
        '<int:pk>/recompute-final/', StudentRecomputeFinalResultView.as_view(),
        name='employee-recompute-final',
    ),
    path('levelup-eligible/', LevelUpEligibleView.as_view(), name='employee-levelup-eligible'),
    path('competency-gap/', CompetencyGapView.as_view(), name='employee-competency-gap'),
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
    path('<int:pk>/create-login/', EmployeeCreateLoginView.as_view(), name='employee-create-login'),
] + automation_router.urls + router.urls
