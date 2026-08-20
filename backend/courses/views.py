import json
import mimetypes

import requests
from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination
from employees.models import Employee

from .models import Course, CourseModule, Enrollment, Lesson, LessonProgress, ScormPackage, ScormTracking
from .scorm import ScormImportError, import_scorm_zip
from .serializers import (
    CourseDetailSerializer,
    CourseModuleSerializer,
    CourseSerializer,
    EnrollmentSerializer,
    LessonProgressSerializer,
    LessonSerializer,
    ScormPackageSerializer,
)
from .services import (
    ValidationError,
    assign_course,
    confirm_offline_completion,
    my_course_detail,
    my_courses,
    offline_completion_report,
    record_lesson_watch_event,
    record_watch_progress,
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


class WatchProgressView(APIView):
    """POST /api/courses/watch-progress/ — body {lesson, position_sec}. Giai doan B: player goi
    DINH KY luc dang PHAT (khong goi khi tua) de nang 'tran' cho phep tua toi da
    (max_watched_sec). Server tu choi buoc nhay lon (xem services.record_watch_progress) - day
    la lop chan tua o SERVER, khong chi dua vao JS client. Tra ve {max_watched_sec, accepted}."""

    def post(self, request):
        employee = _require_learner(request)
        if not employee:
            return Response(
                {'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403,
            )
        try:
            result = record_watch_progress(employee, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result)


class LessonWatchEventView(APIView):
    """POST /api/courses/lesson-watch-event/ — body {lesson, type: paused_face_lost|resumed}.
    Giai doan B: ghi moc tam dung/tiep tuc khi phat hien mat khuon mat luc HOC. KHONG BAO GIO
    nhan/luu anh (khac endpoint proctoring-event cua module thi)."""

    def post(self, request):
        employee = _require_learner(request)
        if not employee:
            return Response(
                {'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403,
            )
        try:
            event = record_lesson_watch_event(employee, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'id': event.id, 'type': event.type, 'created_at': event.created_at})


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


# ==================================================================== Dot 4: SCORM


class ScormUploadView(APIView):
    """POST /api/courses/scorm/upload/ — multipart {lesson: <id>, file: <.zip>}. Chi Admin.
    Giai nen + parse imsmanifest.xml + upload len R2 (xem courses/scorm.py::import_scorm_zip),
    tao/cap nhat ScormPackage 1-1 voi Lesson (type phai la 'scorm')."""

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được upload gói SCORM.'}, status=403)
        lesson = get_object_or_404(Lesson, pk=request.data.get('lesson'), tenant=request.user.tenant)
        zip_file = request.FILES.get('file')
        if not zip_file:
            return Response({'detail': "Cần chọn file .zip ('file')."}, status=400)
        try:
            package = import_scorm_zip(request.user.tenant, lesson, request.user, zip_file)
        except ScormImportError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(ScormPackageSerializer(package).data)


@xframe_options_exempt
def scorm_content(request, package_id, path):
    """GET /api/courses/scorm/<package_id>/content/<path> — proxy-stream 1 file trong goi
    SCORM tu R2, SAME-ORIGIN voi trang phat (scorm_player) de SCO doc duoc window.parent.API
    (xem module docstring courses/scorm.py + ghi chu kien truc trong scorm_player.html).

    KHONG yeu cau dang nhap (giong quy uoc file R2 cong khai khac trong app - course.cover_url,
    lesson.content_url) - noi dung SCORM khong phai du lieu nhay cam, va MOI file con (JS/CSS/
    anh) SCO tu tham chieu qua duong dan tuong doi (trinh duyet tu goi, khong kem duoc header
    Authorization) nen endpoint nay BAT BUOC phai mo, khong the doi hoi JWT header."""
    package = get_object_or_404(ScormPackage, pk=package_id)
    if '..' in path.replace('\\', '/').split('/'):
        raise Http404
    url = f'{settings.R2_PUBLIC_BASE_URL.rstrip("/")}/{package.storage_prefix}{path}'
    try:
        resp = requests.get(url, timeout=15)
    except requests.RequestException as exc:
        raise Http404 from exc
    if resp.status_code != 200:
        raise Http404
    content_type = mimetypes.guess_type(path)[0] or resp.headers.get('Content-Type') or 'application/octet-stream'
    return HttpResponse(resp.content, content_type=content_type)


@xframe_options_exempt
def scorm_player(request, package_id):
    """GET /api/courses/scorm/<package_id>/player/?progress=<lesson_progress_id> — trang phat
    SCORM (HTML/JS thuan, KHONG phai React) do CHINH Django serve, gan window.API/API_1484_11
    bang scorm-again TRUOC KHI tao iframe noi dung - iframe noi dung tro ve scorm_content o
    TREN, cung origin Django nen SCO doc duoc window.parent.API (dung yeu cau same-origin).

    React (khac origin - xem CORS_ALLOWED_ORIGINS) nhung KHONG lien quan: no chi nhung TRANG
    NAY (scorm_player) trong 1 iframe ngoai cung; ben trong trang nay lai co iframe noi dung
    THU HAI, ca hai deu o Django origin -> same-origin voi nhau, thoa dung dieu kien SCORM can.

    Trang nay tu no KHONG doi hoi dang nhap (chi ho tro cac id cong khai) - JWT access token
    duoc React truyen qua URL FRAGMENT (#token=...) luc tao iframe (khong gui len server qua
    query string, tranh lo trong log) roi JS trong trang doc lai de goi state/commit (co
    Authorization header, dung DRF auth binh thuong)."""
    package = get_object_or_404(ScormPackage, pk=package_id)
    progress_id = request.GET.get('progress')
    if not progress_id:
        return HttpResponseBadRequest("Thiếu tham số 'progress'.")

    lib_file = (
        'scorm2004.min.js' if package.version == ScormPackage.Version.SCORM_2004 else 'scorm12.min.js'
    )
    # Duong dan tinh THANG (khong qua {% static %}/ManifestStaticFilesStorage) - tranh phu
    # thuoc vao da chay collectstatic (vd trong test/dev moi clone) de trang phat luon hoat
    # dong duoc; WhiteNoise van serve dung file khong-hash nay o STATIC_URL binh thuong.
    lib_url = f'{settings.STATIC_URL}courses/vendor/{lib_file}'
    config = {
        'isScorm2004': package.version == ScormPackage.Version.SCORM_2004,
        'contentUrl': f'/api/courses/scorm/{package.id}/content/{package.launch_path}',
        'stateUrl': f'/api/courses/scorm/{progress_id}/state/',
        'commitUrl': f'/api/courses/scorm/{progress_id}/commit/',
    }
    # Chan '</script>' pha vo trang neu (khong the xay ra voi cac gia tri tren, nhung phong ho).
    config_json = json.dumps(config).replace('</', '<\\/')
    return render(request, 'courses/scorm_player.html', {
        'lib_url': lib_url, 'config_json': config_json,
    })


def _require_own_lesson_progress(request, progress_id):
    """Dot 4: xac thuc CHINH nguoi hoc so huu LessonProgress nay (dung cho state/commit). Tra
    ve (progress, None) hoac (None, Response loi)."""
    employee = _require_learner(request)
    if not employee:
        return None, Response({'detail': 'Tài khoản này chưa liên kết với hồ sơ nhân sự.'}, status=403)
    progress = (
        LessonProgress.objects.filter(pk=progress_id, enrollment__employee=employee)
        .select_related('lesson', 'enrollment', 'enrollment__employee').first()
    )
    if not progress:
        return None, Response({'detail': 'Không tìm thấy tiến trình bài học.'}, status=404)
    return progress, None


class ScormStateView(APIView):
    """GET /api/courses/scorm/<progress_id>/state/ — tra cmi_json da luu (resume) hoac rong
    neu chua hoc lan nao. Chi CHINH nguoi hoc so huu progress do."""

    def get(self, request, progress_id):
        progress, error = _require_own_lesson_progress(request, progress_id)
        if error:
            return error
        tracking = ScormTracking.objects.filter(lesson_progress=progress).first()
        return Response({
            'cmi_json': tracking.cmi_json if tracking else {},
            'lesson_status': tracking.lesson_status if tracking else '',
            'score_raw': tracking.score_raw if tracking else None,
        })


class ScormCommitView(APIView):
    """POST /api/courses/scorm/<progress_id>/commit/ — body = CommitObject chuan hoa cua
    scorm-again (can renderCommonCommitFields=true o client): {completionStatus, successStatus,
    score: {raw, scaled, ...}, runtimeData, ...} - CUNG 1 hinh dang cho ca SCORM 1.2 va 2004
    (thu vien tu quy doi cmi.core.lesson_status cua 1.2 ve completionStatus/successStatus).

    Hoan thanh khi completionStatus='completed' HOAC successStatus='passed' (dung y prompt).
    Luu ScormTracking, roi neu hoan thanh -> goi lai save_lesson_progress(mark_done=True) -
    TAI DUNG NGUYEN VEN luong hien co (Enrollment->completed, on_course_completed: dong bo ho
    so + xAPI + chung chi - xem courses/services.py), KHONG viet lai (yeu cau an toan cua
    prompt Dot 4)."""

    def post(self, request, progress_id):
        progress, error = _require_own_lesson_progress(request, progress_id)
        if error:
            return error

        payload = request.data or {}
        completion_status = payload.get('completionStatus') or ''
        success_status = payload.get('successStatus') or ''
        score = payload.get('score') or {}
        score_raw = score.get('raw')
        if score_raw is None:
            score_raw = score.get('scaled')

        ScormTracking.objects.update_or_create(
            lesson_progress=progress,
            defaults={
                'tenant': progress.tenant, 'cmi_json': payload.get('runtimeData') or {},
                'lesson_status': completion_status, 'score_raw': score_raw,
            },
        )

        is_complete = completion_status == 'completed' or success_status == 'passed'
        if is_complete and progress.status != LessonProgress.Status.DONE:
            save_lesson_progress(
                progress.enrollment.employee, {'lesson': progress.lesson_id, 'mark_done': True},
            )
        return Response({'ok': True})
