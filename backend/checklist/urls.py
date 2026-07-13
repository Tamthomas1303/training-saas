from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ChecklistViewSet, EmployeeChecklistView, TrainingProgressSaveView

router = DefaultRouter()
router.register('', ChecklistViewSet, basename='checklist')

urlpatterns = [
    path('training/save/', TrainingProgressSaveView.as_view(), name='training-save'),
    path('training/', EmployeeChecklistView.as_view(), name='training-checklist'),
] + router.urls
