import secrets

from rest_framework import viewsets

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination

from .models import Cohort, CohortSession, Program, ProgramContent
from .serializers import (
    CohortSerializer,
    CohortSessionSerializer,
    ProgramContentSerializer,
    ProgramSerializer,
)


class AdminOmWriteMixin:
    """Đọc: mọi role đăng nhập. Ghi (thêm/sửa/xóa): chỉ Admin/OM (Phòng Đào tạo)."""

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and (request.user.role or '').lower() not in {'admin', 'om'}:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Chỉ Admin/OM được thêm/sửa/xóa mục này.')


class ProgramViewSet(AdminOmWriteMixin, TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ProgramSerializer
    queryset = Program.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['audience', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class ProgramContentViewSet(AdminOmWriteMixin, TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ProgramContentSerializer
    queryset = ProgramContent.objects.all()
    pagination_class = None
    filterset_fields = ['program']
    ordering = ['order']


class CohortViewSet(AdminOmWriteMixin, TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CohortSerializer
    queryset = Cohort.objects.select_related('program').all()
    pagination_class = DefaultPagination
    filterset_fields = ['program', 'status']
    search_fields = ['name', 'location']
    ordering_fields = ['start_date', 'created_at', 'name']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)


class CohortSessionViewSet(AdminOmWriteMixin, TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CohortSessionSerializer
    queryset = CohortSession.objects.all()
    pagination_class = None
    filterset_fields = ['cohort']
    ordering = ['date', 'session_no']

    def perform_create(self, serializer):
        # Sinh mã QR tự điểm danh khi tạo buổi (học viên quét để tự điểm danh — M2.3).
        serializer.save(tenant=self.request.user.tenant, qr_token=secrets.token_urlsafe(24))
