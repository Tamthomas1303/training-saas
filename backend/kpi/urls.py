from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AllowanceDataView,
    AllowanceExportView,
    CommissionListView,
    CommissionMarkPaidView,
    CommissionRecomputeAllView,
    KpiHourTargetViewSet,
    KpiModeView,
    KpiReportDataView,
    KpiReportExportView,
    KpiSessionSaveView,
    KpiSessionViewSet,
    KpiStatsView,
    KpiTopicsView,
)

router = DefaultRouter()
router.register('sessions', KpiSessionViewSet, basename='kpi-session')
# Muc 11 muc 3 - CRUD muc tieu gio dao tao/thang theo vi tri.
router.register('hour-targets', KpiHourTargetViewSet, basename='kpi-hour-target')

urlpatterns = [
    path('topics/', KpiTopicsView.as_view(), name='kpi-topics'),
    path('sessions/save/', KpiSessionSaveView.as_view(), name='kpi-session-save'),
    path('stats/', KpiStatsView.as_view(), name='kpi-stats'),
    path('mode/', KpiModeView.as_view(), name='kpi-mode'),
    path('report/', KpiReportDataView.as_view(), name='kpi-report'),
    path('report/export/', KpiReportExportView.as_view(), name='kpi-report-export'),
    path('allowance/', AllowanceDataView.as_view(), name='kpi-allowance'),
    path('allowance/export/', AllowanceExportView.as_view(), name='kpi-allowance-export'),
    path('commission/', CommissionListView.as_view(), name='commission-list'),
    path('commission/recompute/', CommissionRecomputeAllView.as_view(), name='commission-recompute'),
    path('commission/<int:pk>/mark-paid/', CommissionMarkPaidView.as_view(), name='commission-mark-paid'),
] + router.urls
