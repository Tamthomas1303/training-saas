import secrets

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination

from .models import Cohort, CohortSession, Enrollment, Program, ProgramContent
from .serializers import (
    CohortSerializer,
    CohortSessionSerializer,
    ProgramContentSerializer,
    ProgramSerializer,
)
from .services import mark_attendance, session_roster

# Người phụ trách được điều chỉnh điểm danh bằng tay.
ATTENDANCE_MANAGE_ROLES = {'admin', 'om', 'trainer', 'bql'}


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


class SessionAttendanceView(APIView):
    """GET /api/sourcing/cohort-sessions/<id>/attendance/ — danh sách điểm danh buổi.
    POST — người phụ trách điều chỉnh tay: {enrollment, present}."""

    def get(self, request, pk):
        session = get_object_or_404(CohortSession, pk=pk, tenant=request.user.tenant)
        return Response({
            'session': CohortSessionSerializer(session).data,
            'roster': session_roster(session),
        })

    def post(self, request, pk):
        if (request.user.role or '').lower() not in ATTENDANCE_MANAGE_ROLES:
            return Response({'detail': 'Bạn không có quyền điều chỉnh điểm danh.'}, status=403)
        session = get_object_or_404(CohortSession, pk=pk, tenant=request.user.tenant)
        enrollment = get_object_or_404(
            Enrollment, pk=request.data.get('enrollment'), cohort=session.cohort, tenant=request.user.tenant,
        )
        present = bool(request.data.get('present', True))
        _, err = mark_attendance(session, enrollment, present=present, method='manual', user=request.user)
        if err:
            return Response({'detail': err}, status=400)
        return Response({'roster': session_roster(session)})


class AttendInfoView(APIView):
    """GET /api/sourcing/attend/<token>/ — trang công khai học viên quét QR mở ra (không cần đăng
    nhập): thông tin buổi + danh sách học viên để tự chọn tên điểm danh."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        session = get_object_or_404(CohortSession, qr_token=token)
        return Response({
            'session': {
                'title': session.title,
                'session_no': session.session_no,
                'date': session.date.isoformat() if session.date else None,
                'location': session.location,
            },
            'cohort': session.cohort.name,
            'program': session.cohort.program.name,
            'roster': [
                {
                    'enrollment_id': r['enrollment_id'],
                    'employee_name': r['employee_name'],
                    'employee_code': r['employee_code'],
                    'present': r['present'],
                }
                for r in session_roster(session)
            ],
        })


class AttendCheckInView(APIView):
    """POST /api/sourcing/attend/<token>/checkin/ — học viên tự điểm danh: {enrollment}."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token):
        session = get_object_or_404(CohortSession, qr_token=token)
        enrollment = get_object_or_404(Enrollment, pk=request.data.get('enrollment'), cohort=session.cohort)
        _, err = mark_attendance(session, enrollment, present=True, method='self')
        if err:
            return Response({'detail': err}, status=400)
        return Response({'ok': True, 'name': enrollment.employee.name})
