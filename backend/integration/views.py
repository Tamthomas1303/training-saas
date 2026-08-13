from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination

from .models import CertificateIssued, CertificateTemplate, CertProgram, XapiStatement
from .serializers import (
    CertificateIssuedSerializer,
    CertificateTemplateSerializer,
    CertProgramSerializer,
    XapiStatementSerializer,
)
from .services import reissue_certificate


def _require_admin_write(request):
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and (request.user.role or '').lower() != 'admin':
        raise PermissionDenied('Chỉ Admin được thêm/sửa/xóa dữ liệu chứng chỉ.')


def _require_learner(request):
    return getattr(request.user, 'employee', None)


class CertificateTemplateViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD mau chung chi (anh nen + toa do o chu). Ghi: chi Admin."""

    serializer_class = CertificateTemplateSerializer
    queryset = CertificateTemplate.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['type', 'active']
    ordering = ['-created_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class CertProgramViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD chuong trinh chung chi. Ghi: chi Admin."""

    serializer_class = CertProgramSerializer
    queryset = CertProgram.objects.select_related('certificate_template').all()
    pagination_class = DefaultPagination
    filterset_fields = ['type', 'active']
    ordering = ['-created_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class CertificateIssuedViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Danh sach chung chi da cap - chi doc, chi Admin. Loc theo employee=<id>, ref_type=<...>."""

    serializer_class = CertificateIssuedSerializer
    queryset = CertificateIssued.objects.select_related('employee', 'program').all()
    pagination_class = DefaultPagination
    filterset_fields = ['employee', 'ref_type', 'program']
    ordering = ['-issued_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (request.user.role or '').lower() != 'admin':
            raise PermissionDenied('Chỉ Admin được xem danh sách chứng chỉ.')


class ReissueCertificateView(APIView):
    """POST /api/integration/certificates/<id>/reissue/ — sinh lại PDF (vd sau khi sửa tọa độ
    fields_config), giữ nguyên mã/ngày cấp cũ. Chỉ Admin."""

    def post(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được cấp lại chứng chỉ.'}, status=403)
        certificate = get_object_or_404(CertificateIssued, pk=pk, tenant=request.user.tenant)
        certificate = reissue_certificate(certificate)
        return Response(CertificateIssuedSerializer(certificate).data)


class MyCertificatesView(APIView):
    """GET /api/integration/my-certificates/ — chứng chỉ của CHÍNH request.user (map qua
    Employee.user, giống courses.views.MyCoursesView)."""

    def get(self, request):
        employee = _require_learner(request)
        if not employee:
            return Response({'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403)
        certs = CertificateIssued.objects.filter(employee=employee).select_related('program')
        return Response(CertificateIssuedSerializer(certs, many=True).data)


class TemplateImageUploadView(APIView):
    """POST /api/integration/templates/upload/ — body {image: data:...}. Upload anh nen mau
    chung chi len R2, tra ve URL de luu vao CertificateTemplate.template_pdf_url (PhotoSlot tra
    ve data: URL, KHONG luu thang duoc vao URLField - can qua buoc nay, giong
    accounts.views.ChangeAvatarView). Chi Admin."""

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được tải mẫu chứng chỉ.'}, status=403)
        from checklist.storage import StorageError, is_data_url, upload_data_url

        value = request.data.get('image')
        if not value or not is_data_url(value):
            return Response({'detail': 'Cần ảnh hợp lệ (data URL).'}, status=400)
        try:
            url = upload_data_url(value, f'certificate-templates/{request.user.tenant_id}', 'template')
        except StorageError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'url': url})


class XapiStatementViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Nhat ky xAPI - chi doc, chi Admin. MVP xem noi bo (chua day LRS ngoai)."""

    serializer_class = XapiStatementSerializer
    queryset = XapiStatement.objects.select_related('employee').all()
    pagination_class = DefaultPagination
    filterset_fields = ['employee', 'verb', 'object_type']
    ordering = ['-timestamp']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (request.user.role or '').lower() != 'admin':
            raise PermissionDenied('Chỉ Admin được xem nhật ký xAPI.')
