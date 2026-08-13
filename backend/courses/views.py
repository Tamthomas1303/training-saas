from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination
from employees.models import Employee

from .models import Course, CourseModule, Enrollment, Lesson
from .serializers import (
    CourseDetailSerializer,
    CourseModuleSerializer,
    CourseSerializer,
    EnrollmentSerializer,
    LessonProgressSerializer,
    LessonSerializer,
)
from .services import (
    ValidationError,
    assign_course,
    confirm_offline_completion,
    my_course_detail,
    my_courses,
    offline_completion_report,
    reorder_items,
    save_lesson_progress,
)


def _require_admin_write(request):
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and (request.user.role or '').lower() != 'admin':
        raise PermissionDenied('Chỉ Admin được thêm/sửa/xóa khóa học.')


def _require_learner(request):
    """Tra ve Employee cua request.user, hoac None neu tai khoan chua duoc lien ket (xem
    Employee.user - man Nhan su co nut 'Tao tai khoan dang nhap')."""
    return getattr(request.user, 'employee', None)


def _require_training_staff(request):
    """Dot 3 phan B: 'moi vai tro dao tao deu duoc' xac nhan hoan thanh ho - tuc la MOI role
    TRU 'employee' (tai khoan hoc vien, khong phai nguoi dao tao). Chot cua anh Chung."""
    if (request.user.role or '').lower() == 'employee':
        raise PermissionDenied('Tài khoản học viên không được xác nhận hoàn thành hộ.')


class CourseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD khoa hoc. Doc: moi role dang nhap (gom ca hoc vien, tuy EmployeeLearnerScope van
    cho qua vi cung /api/courses/). Ghi (them/sua/xoa): chi Admin - dung quy uoc voi
    Checklist/Document."""

    queryset = Course.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['status']
    search_fields = ['title']
    ordering_fields = ['title', 'created_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant, created_by=self.request.user)


class CourseModuleViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD chuong. Loc theo course=<id>. Ghi: chi Admin."""

    serializer_class = CourseModuleSerializer
    queryset = CourseModule.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['course']
    ordering = ['order']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)


class LessonViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD bai hoc. Loc theo module=<id>. Ghi: chi Admin."""

    serializer_class = LessonSerializer
    queryset = Lesson.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['module']
    ordering = ['order']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_admin_write(request)


class EnrollmentViewSet(TenantScopedViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Danh sach ghi danh - chi doc, chi Admin (xem ai da duoc gan 1 khoa). Tao qua
    CourseAssignView, khong CRUD truc tiep o day."""

    serializer_class = EnrollmentSerializer
    queryset = Enrollment.objects.select_related('course', 'employee', 'assigned_by').all()
    pagination_class = DefaultPagination
    filterset_fields = ['course', 'employee', 'status']
    ordering = ['-created_at']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if (request.user.role or '').lower() != 'admin':
            raise PermissionDenied('Chỉ Admin được xem danh sách ghi danh.')


class ReorderView(APIView):
    """POST /api/courses/reorder/ — body {model: 'module'|'lesson', items: [{id, order}, ...]}.
    Chi Admin. Dung cho keo-tha sap thu tu chuong/bai o man quan tri."""

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được sắp xếp lại thứ tự.'}, status=403)
        model_name = request.data.get('model')
        items = request.data.get('items') or []
        model = {'module': CourseModule, 'lesson': Lesson}.get(model_name)
        if not model or not items:
            return Response({'detail': "Cần 'model' (module|lesson) và 'items'."}, status=400)
        updated = reorder_items(model, request.user.tenant, items)
        return Response({'updated': updated})


class CourseAssignView(APIView):
    """POST /api/courses/<id>/assign/ — body {employee_ids: [...]} HOẶC {position?,
    restaurant_id?, group?}. Chi Admin. Bulk tao Enrollment, bo qua nhan su da ghi danh."""

    def post(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được gán khóa học.'}, status=403)
        course = get_object_or_404(Course, pk=pk, tenant=request.user.tenant)
        try:
            created = assign_course(request.user, course, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'created': created})


class MyCoursesView(APIView):
    """GET /api/courses/my/ — danh sach khoa da ghi danh cua request.user (map qua
    Employee.user) + % tien do moi khoa."""

    def get(self, request):
        employee = _require_learner(request)
        if not employee:
            return Response(
                {'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403,
            )
        return Response(my_courses(employee))


class MyCourseDetailView(APIView):
    """GET /api/courses/my/<course_id>/ — chi tiet 1 khoa da ghi danh: cay chuong->bai +
    progress tung bai."""

    def get(self, request, course_id):
        employee = _require_learner(request)
        if not employee:
            return Response(
                {'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403,
            )
        detail = my_course_detail(employee, course_id)
        if detail is None:
            return Response({'detail': 'Bạn chưa được gán khóa học này.'}, status=404)
        return Response(detail)


class ProgressSaveView(APIView):
    """POST /api/courses/progress/ — cap nhat tien do 1 bai cua CHINH nguoi goi (map qua
    Employee.user)."""

    def post(self, request):
        employee = _require_learner(request)
        if not employee:
            return Response(
                {'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403,
            )
        try:
            progress = save_lesson_progress(employee, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(LessonProgressSerializer(progress).data)


class OfflineConfirmView(APIView):
    """POST /api/courses/offline-confirm/ — body {employee, target_type: lesson|course,
    target_id, method, note?, evidence_url?}. Dot 3 phan B: 'moi vai tro dao tao' duoc xac
    nhan hoan thanh HO cho 1 nhan su (khong qua player) - xem
    courses.services.confirm_offline_completion."""

    def post(self, request):
        _require_training_staff(request)
        employee = get_object_or_404(Employee, pk=request.data.get('employee'), tenant=request.user.tenant)
        target_type = request.data.get('target_type')
        target_id = request.data.get('target_id')
        method = request.data.get('method') or 'kem_tai_cho'
        note = request.data.get('note', '')
        evidence_url = request.data.get('evidence_url', '')
        if not target_id:
            return Response({'detail': "Cần 'target_id'."}, status=400)
        try:
            enrollment = confirm_offline_completion(
                request.user, employee, target_type, target_id, method, note, evidence_url,
            )
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EnrollmentSerializer(enrollment).data)


class OfflineReportView(APIView):
    """GET /api/courses/<id>/offline-report/ — ty le hoan thanh online vs offline cua 1 khoa
    (don gian, dung y prompt Dot 3 phan B). Chi Admin."""

    def get(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được xem báo cáo.'}, status=403)
        get_object_or_404(Course, pk=pk, tenant=request.user.tenant)
        return Response(offline_completion_report(pk, request.user.tenant))
