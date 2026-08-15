from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CompetencyGroupViewSet,
    CompetencyViewSet,
    DashboardIndicatorViewSet,
    Employee360View,
    EmployeeSearchView,
    ImportPositionGroupWeightsView,
    ImportPositionTargetsView,
    PositionGroupWeightViewSet,
    PositionTargetViewSet,
    SeedDefaultsView,
)

router = DefaultRouter()
router.register('competency-groups', CompetencyGroupViewSet, basename='competency-group')
router.register('competencies', CompetencyViewSet, basename='competency')
router.register('position-targets', PositionTargetViewSet, basename='position-target')
router.register('position-weights', PositionGroupWeightViewSet, basename='position-weight')
router.register('indicators', DashboardIndicatorViewSet, basename='dashboard-indicator')

urlpatterns = [
    path('employees/', EmployeeSearchView.as_view(), name='dashboard-employee-search'),
    path('employee/<str:id_or_code>/', Employee360View.as_view(), name='dashboard-employee-360'),
    path('seed-defaults/', SeedDefaultsView.as_view(), name='dashboard-seed-defaults'),
    path('import/targets/', ImportPositionTargetsView.as_view(), name='dashboard-import-targets'),
    path('import/weights/', ImportPositionGroupWeightsView.as_view(), name='dashboard-import-weights'),
] + router.urls
