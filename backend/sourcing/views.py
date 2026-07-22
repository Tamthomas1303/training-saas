import secrets

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination

from employees.models import Employee

from .models import Cohort, CohortSession, Enrollment, Program, ProgramContent
from .serializers import (
    CohortSerializer,
    CohortSessionSerializer,
    EnrollmentSerializer,
    ProgramContentSerializer,
    ProgramSerializer,
)
from .services import (
    enrollment_contents,
    enrollment_summary,
    finalize_enrollment,
    mark_attendance,
    session_roster,
    toggle_content,
)

# Người phụ trách được điều chỉnh điểm danh bằng tay.
ATTENDANCE_MANAGE_ROLES = {'admin', 'om', 'trainer', 'bql'}
# Admin/BQL thêm/xoá học viên vào đợt + chốt kết quả.
ENROLLMENT_MANAGE_ROLES = {'admin', 'om', 'bql'}


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


class EnrollmentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """Học viên trong đợt. Đọc: mọi role. Thêm/xoá: Admin/OM/BQL. Lọc ?cohort= &status=."""

    serializer_class = EnrollmentSerializer
    queryset = Enrollment.objects.select_related('employee', 'employee__restaurant').all()
    pagination_class = None
    filterset_fields = ['cohort', 'status', 'employee']
    ordering = ['employee__name']

    def _require_manage(self):
        if (self.request.user.role or '').lower() not in ENROLLMENT_MANAGE_ROLES:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Chỉ Admin/OM/BQL được thêm/xoá học viên.')

    def create(self, request, *args, **kwargs):
        self._require_manage()
        cohort = get_object_or_404(Cohort, pk=request.data.get('cohort'), tenant=request.user.tenant)
        employee = get_object_or_404(Employee, pk=request.data.get('employee'), tenant=request.user.tenant)
        if Enrollment.objects.filter(cohort=cohort, employee=employee).exists():
            return Response({'detail': 'Học viên đã có trong đợt này.'}, status=400)
        enrollment = Enrollment.objects.create(
            tenant=request.user.tenant, cohort=cohort, employee=employee, added_by=request.user,
        )
        return Response(EnrollmentSerializer(enrollment).data, status=201)

    def destroy(self, request, *args, **kwargs):
        self._require_manage()
        return super().destroy(request, *args, **kwargs)


class EnrollmentContentsView(APIView):
    """GET /api/sourcing/enrollments/<id>/contents/ — checklist nội dung + tiến độ + tóm tắt.
    POST — đánh dấu 1 mục: {content, done} (người phụ trách)."""

    def get(self, request, pk):
        enrollment = get_object_or_404(Enrollment, pk=pk, tenant=request.user.tenant)
        return Response({
            'enrollment': EnrollmentSerializer(enrollment).data,
            'contents': enrollment_contents(enrollment),
            'summary': enrollment_summary(enrollment),
        })

    def post(self, request, pk):
        if (request.user.role or '').lower() not in ATTENDANCE_MANAGE_ROLES:
            return Response({'detail': 'Bạn không có quyền cập nhật nội dung.'}, status=403)
        enrollment = get_object_or_404(Enrollment, pk=pk, tenant=request.user.tenant)
        content = get_object_or_404(ProgramContent, pk=request.data.get('content'), tenant=request.user.tenant)
        _, err = toggle_content(enrollment, content, bool(request.data.get('done')))
        if err:
            return Response({'detail': err}, status=400)
        return Response({
            'contents': enrollment_contents(enrollment),
            'summary': enrollment_summary(enrollment),
        })


class EnrollmentResultView(APIView):
    """POST /api/sourcing/enrollments/<id>/result/ — chốt kết quả {result: Đạt|Không đạt}.
    Chỉ Admin/OM/BQL."""

    def post(self, request, pk):
        if (request.user.role or '').lower() not in ENROLLMENT_MANAGE_ROLES:
            return Response({'detail': 'Chỉ Admin/OM/BQL được chốt kết quả.'}, status=403)
        enrollment = get_object_or_404(Enrollment, pk=pk, tenant=request.user.tenant)
        _, err = finalize_enrollment(enrollment, request.data.get('result'))
        if err:
            return Response({'detail': err}, status=400)
        return Response(EnrollmentSerializer(enrollment).data)


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
