from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardStatsView,
    EmployeeViewSet,
    HomeStatsView,
    LevelUpOptionsView,
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
    path('import-file/', RecruitmentImportFileView.as_view(), name='recruitment-import-file'),
    path('dashboard/', DashboardStatsView.as_view(), name='employee-dashboard'),
    path('home/', HomeStatsView.as_view(), name='employee-home'),
    path('<int:pk>/detail/', StudentDetailView.as_view(), name='employee-detail'),
    path('<int:pk>/change-status/', StudentChangeStatusView.as_view(), name='employee-change-status'),
    path('<int:pk>/office-result/', StudentOfficeResultView.as_view(), name='employee-office-result'),
    path('<int:pk>/levelup-options/', LevelUpOptionsView.as_view(), name='employee-levelup-options'),
    path(
        '<int:pk>/export-probation-result/', StudentExportProbationResultView.as_view(),
        name='employee-export-probation-result',
    ),
] + router.urls
