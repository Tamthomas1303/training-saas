from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CertificateIssuedViewSet,
    CertificateTemplateViewSet,
    CertProgramViewSet,
    MyCertificatesView,
    ReissueCertificateView,
    TemplateImageUploadView,
    XapiStatementViewSet,
)

router = DefaultRouter()
router.register('templates', CertificateTemplateViewSet, basename='cert-template')
router.register('programs', CertProgramViewSet, basename='cert-program')
router.register('certificates', CertificateIssuedViewSet, basename='cert-issued')
router.register('xapi', XapiStatementViewSet, basename='xapi-statement')

urlpatterns = [
    path('my-certificates/', MyCertificatesView.as_view(), name='cert-my'),
    path('certificates/<int:pk>/reissue/', ReissueCertificateView.as_view(), name='cert-reissue'),
    path('templates/upload/', TemplateImageUploadView.as_view(), name='cert-template-upload'),
] + router.urls
