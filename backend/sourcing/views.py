import secrets

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination

from employees.models import Employee

from .models import Cohort, CohortSession, Enrollment, Program, ProgramContent, TrainingContent
from .serializers import (
    CohortSerializer,
    CohortSessionSerializer,
    EnrollmentSerializer,
    ProgramContentSerializer,
    ProgramSerializer,
    TrainingContentSerializer,
)
from .models import Notification
from .services import (
    bulk_enroll_and_invite,
    cohort_report,
    enrollment_contents,
    enrollment_summary,
    finalize_enrollment,
    mark_attendance,
    notify_enrollment_added,
    notify_enrollment_result,
    notify_session_created,
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
    filterset_fields = ['audience', 'mode', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class TrainingContentViewSet(AdminOmWriteMixin, TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """Danh mục nội dung đào tạo (Admin/OM thêm/bớt)."""

    serializer_class = TrainingContentSerializer
    queryset = TrainingContent.objects.all()
    pagination_class = None
    filterset_fields = ['category', 'is_active', 'is_prerequisite']
    search_fields = ['name', 'code', 'target_roles']
    ordering = ['order', 'name']


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
        serializer.save(
            tenant=self.request.user.tenant, created_by=self.request.user,
            qr_token=secrets.token_urlsafe(24),
        )


class CohortSessionViewSet(AdminOmWriteMixin, TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CohortSessionSerializer
    queryset = CohortSession.objects.all()
    pagination_class = None
    filterset_fields = ['cohort']
    ordering = ['date', 'session_no']

    def perform_create(self, serializer):
        # Sinh mã QR tự điểm danh khi tạo buổi (học viên quét để tự điểm danh — M2.3).
        session = serializer.save(tenant=self.request.user.tenant, qr_token=secrets.token_urlsafe(24))
        notify_session_created(session)


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
        notify_enrollment_added(enrollment)
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
        notify_enrollment_result(enrollment)
        return Response(EnrollmentSerializer(enrollment).data)


class NotificationListView(APIView):
    """GET /api/sourcing/notifications/ — thông báo của chính user + số chưa đọc.
    POST — đánh dấu đã đọc: {id} (một) hoặc {all: true} (tất cả)."""

    def get(self, request):
        qs = Notification.objects.filter(tenant=request.user.tenant, user=request.user)[:50]
        items = [
            {
                'id': n.id, 'title': n.title, 'body': n.body, 'link': n.link,
                'category': n.category, 'is_read': n.is_read,
                'created_at': n.created_at.isoformat(),
            }
            for n in qs
        ]
        unread = Notification.objects.filter(
            tenant=request.user.tenant, user=request.user, is_read=False,
        ).count()
        return Response({'items': items, 'unread': unread})

    def post(self, request):
        base = Notification.objects.filter(tenant=request.user.tenant, user=request.user, is_read=False)
        if request.data.get('all'):
            base.update(is_read=True)
        elif request.data.get('id'):
            base.filter(pk=request.data.get('id')).update(is_read=True)
        unread = Notification.objects.filter(
            tenant=request.user.tenant, user=request.user, is_read=False,
        ).count()
        return Response({'unread': unread})


class CohortBulkEnrollView(APIView):
    """POST /api/sourcing/cohorts/<id>/bulk-enroll/ — lọc nhân sự theo tiêu chí & mời hàng loạt
    (thêm vào đợt + gửi thông báo/email). Body: restaurant/level_group/operation_unit/position
    hoặc employee_ids. Chỉ Admin/OM/BQL."""

    def post(self, request, pk):
        if (request.user.role or '').lower() not in ENROLLMENT_MANAGE_ROLES:
            return Response({'detail': 'Chỉ Admin/OM/BQL được mời hàng loạt.'}, status=403)
        cohort = get_object_or_404(Cohort, pk=pk, tenant=request.user.tenant)
        result = bulk_enroll_and_invite(cohort, request.user, request.data or {})
        return Response(result)


class CohortReportView(APIView):
    """GET /api/sourcing/cohorts/<id>/report/ — báo cáo tham gia (mời vs có mặt)."""

    def get(self, request, pk):
        cohort = get_object_or_404(Cohort, pk=pk, tenant=request.user.tenant)
        return Response(cohort_report(cohort))


class EventInfoView(APIView):
    """GET /api/sourcing/event/<token>/ — QR cấp sự kiện (cohort): học viên chọn CHỦ ĐỀ/buổi rồi
    điểm danh. Công khai."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        cohort = get_object_or_404(Cohort, qr_token=token)
        sessions = CohortSession.objects.filter(cohort=cohort).order_by('date', 'session_no')
        roster = [
            {'enrollment_id': r['enrollment_id'], 'employee_name': r['employee_name'], 'employee_code': r['employee_code']}
            for r in session_roster(sessions.first()) if sessions.exists()
        ] if sessions.exists() else []
        return Response({
            'cohort': cohort.name,
            'program': cohort.program.name,
            'sessions': [
                {'id': s.id, 'session_no': s.session_no,
                 'title': s.title or f'Buổi {s.session_no}', 'date': s.date.isoformat() if s.date else None}
                for s in sessions
            ],
            'roster': roster,
        })


class EventCheckInView(APIView):
    """POST /api/sourcing/event/<token>/checkin/ — {session, enrollment}. Công khai."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, token):
        cohort = get_object_or_404(Cohort, qr_token=token)
        session = get_object_or_404(CohortSession, pk=request.data.get('session'), cohort=cohort)
        enrollment = get_object_or_404(Enrollment, pk=request.data.get('enrollment'), cohort=cohort)
        _, err = mark_attendance(session, enrollment, present=True, method='self')
        if err:
            return Response({'detail': err}, status=400)
        return Response({'ok': True, 'name': enrollment.employee.name, 'session': session.title or session.session_no})


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
