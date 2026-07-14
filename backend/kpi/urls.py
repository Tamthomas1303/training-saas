from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AllowanceDataView,
    AllowanceExportView,
    CommissionListView,
    CommissionMarkPaidView,
    CommissionRecomputeAllView,
    KpiReportDataView,
    KpiReportExportView,
    KpiSessionSaveView,
    KpiSessionViewSet,
    KpiStatsView,
    KpiTopicsView,
)

router = DefaultRouter()
router.register('sessions', KpiSessionViewSet, basename='kpi-session')

urlpatterns = [
    path('topics/', KpiTopicsView.as_view(), name='kpi-topics'),
    path('sessions/save/', KpiSessionSaveView.as_view(), name='kpi-session-save'),
    path('stats/', KpiStatsView.as_view(), name='kpi-stats'),
    path('report/', KpiReportDataView.as_view(), name='kpi-report'),
    path('report/export/', KpiReportExportView.as_view(), name='kpi-report-export'),
    path('allowance/', AllowanceDataView.as_view(), name='kpi-allowance'),
    path('allowance/export/', AllowanceExportView.as_view(), name='kpi-allowance-export'),
    path('commission/', CommissionListView.as_view(), name='commission-list'),
    path('commission/recompute/', CommissionRecomputeAllView.as_view(), name='commission-recompute'),
    path('commission/<int:pk>/mark-paid/', CommissionMarkPaidView.as_view(), name='commission-mark-paid'),
] + router.urls
