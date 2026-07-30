from django.urls import path

from .views import TrainingReportPreviewView, TrainingReportSendView

urlpatterns = [
    path('training/preview/', TrainingReportPreviewView.as_view(), name='report-training-preview'),
    path('training/send/', TrainingReportSendView.as_view(), name='report-training-send'),
]
