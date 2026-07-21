from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DashboardStatsView,
    EmployeeViewSet,
    HomeStatsView,
    PositionListView,
    StudentChangeStatusView,
    StudentDetailView,
    StudentExportProbationResultView,
)

router = DefaultRouter()
router.register('', EmployeeViewSet, basename='employee')

urlpatterns = [
    path('positions/', PositionListView.as_view(), name='employee-positions'),
    path('dashboard/', DashboardStatsView.as_view(), name='employee-dashboard'),
    path('home/', HomeStatsView.as_view(), name='employee-home'),
    path('<int:pk>/detail/', StudentDetailView.as_view(), name='employee-detail'),
    path('<int:pk>/change-status/', StudentChangeStatusView.as_view(), name='employee-change-status'),
    path(
        '<int:pk>/export-probation-result/', StudentExportProbationResultView.as_view(),
        name='employee-export-probation-result',
    ),
] + router.urls
