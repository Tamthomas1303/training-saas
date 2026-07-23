from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination

from .dashboard import dashboard_payload
from .detail import export_probation_result_pdf, student_detail
from .home import home_payload
from .models import Employee
from .serializers import EmployeeSerializer
from .services import change_employee_status

STUDENT_ADMIN_ROLES = {'admin', 'om', 'bql', 'trainer'}


TRAINING_STATUS_FILTERS = {'in_progress', 'not_started', 'done'}


class EmployeeViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.select_related('restaurant', 'trainer').all()
    pagination_class = DefaultPagination
    filterset_fields = ['restaurant', 'employee_status', 'operation_unit', 'level_group', 'is_legacy']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'start_date']
    ordering = ['name']

    def get_queryset(self):
        """training_status: loc theo % tien do checklist (khong phai field DB nen tinh hang
        loat roi loc lai theo id, xem batch_checklist_progress_percent) - dung chung khai
        niem voi khoi dashboard."""
        qs = super().get_queryset()

        # Lọc theo phạm vi nhà hàng: BQL/Trainer/KCS chỉ thấy nhân sự nhà hàng mình phụ trách
        # (port tinh thần scope hệ cũ). Admin/OM/BOD/AM = toàn hệ thống.
        from employees.permissions import get_restaurant_scope

        scope = get_restaurant_scope(self.request.user)
        if not scope['all']:
            qs = qs.filter(restaurant_id__in=scope['restaurant_ids'])

        training_status = self.request.query_params.get('training_status')
        if training_status in TRAINING_STATUS_FILTERS:
            from .services import batch_checklist_progress_percent

            progress_map = batch_checklist_progress_percent(qs)
            matching_ids = [
                emp_id for emp_id, percent in progress_map.items()
                if (training_status == 'in_progress' and 0 < percent < 100)
                or (training_status == 'not_started' and percent == 0)
                or (training_status == 'done' and percent == 100)
            ]
            qs = qs.filter(id__in=matching_ids)
        return qs

    def _require_write(self):
        """Chỉ Admin/OM được thêm/sửa/xóa nhân sự."""
        if (self.request.user.role or '').lower() not in {'admin', 'om'}:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Chỉ Admin/OM được thêm/sửa/xóa nhân sự.')

    def create(self, request, *args, **kwargs):
        self._require_write()
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        self._require_write()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._require_write()
        return super().destroy(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        """Batch tinh progress_percent + lms_marks cho ca trang (thay vi tung dong trong
        serializer) de tranh N+1 - xem services.batch_checklist_progress_percent/
        batch_lms_marks."""
        from .services import batch_checklist_progress_percent, batch_lms_marks

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        objects = page if page is not None else queryset

        context = self.get_serializer_context()
        context['progress_map'] = batch_checklist_progress_percent(objects)
        context['lms_marks_map'] = batch_lms_marks(objects)
        serializer = self.get_serializer(objects, many=True, context=context)

        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class PositionListView(APIView):
    """GET /api/employees/positions/ — danh sách vị trí gợi ý (chọn khi thêm nhân sự), gộp từ
    Checklist + Employee của tenant + các vị trí cấp O chuẩn. Tránh gõ tay sai chính tả."""

    def get(self, request):
        from checklist.models import Checklist

        tenant = request.user.tenant
        positions = set(
            Checklist.objects.filter(tenant=tenant).exclude(position='').values_list('position', flat=True)
        )
        positions |= set(
            Employee.objects.filter(tenant=tenant).exclude(position='').values_list('position', flat=True)
        )
        for std in ('Quản lý nhà hàng', 'Giám sát', 'Bếp trưởng', 'Bếp phó'):
            positions.add(std)
        return Response(sorted(positions))


def _require_data_admin(request):
    if (request.user.role or '').lower() not in {'admin', 'om'}:
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied('Chỉ Admin/OM được nhập/đồng bộ dữ liệu nhân sự.')


class RecruitmentSourceView(APIView):
    """GET/PUT /api/employees/recruitment-source/ — xem & đặt link CSV tự đồng bộ (Cách 3)."""

    def get(self, request):
        from .models import RecruitmentSource

        src = RecruitmentSource.objects.filter(tenant=request.user.tenant).first()
        return Response({'csv_url': src.csv_url if src else ''})

    def put(self, request):
        _require_data_admin(request)
        from .models import RecruitmentSource

        url = (request.data.get('csv_url') or '').strip()
        RecruitmentSource.objects.update_or_create(tenant=request.user.tenant, defaults={'csv_url': url})
        return Response({'csv_url': url})


class HrSyncSourceView(APIView):
    """GET/PUT /api/employees/hr-sync-sources/ — cấu hình link CSV các tab 'Auto Syncing - HR
    Data' (v2.1). GET: liệt kê mọi tab + link hiện có. PUT {kind, csv_url}: đặt link 1 tab."""

    def get(self, request):
        from .models import HrSyncSource

        by_kind = {s.kind: s.csv_url for s in HrSyncSource.objects.filter(tenant=request.user.tenant)}
        return Response([
            {'kind': k, 'label': label, 'csv_url': by_kind.get(k, '')}
            for k, label in HrSyncSource.Kind.choices
        ])

    def put(self, request):
        _require_data_admin(request)
        from .models import HrSyncSource

        kind = (request.data.get('kind') or '').strip()
        if kind not in dict(HrSyncSource.Kind.choices):
            return Response({'detail': 'Loại nguồn không hợp lệ.'}, status=400)
        url = (request.data.get('csv_url') or '').strip()
        HrSyncSource.objects.update_or_create(
            tenant=request.user.tenant, kind=kind, defaults={'csv_url': url},
        )
        return Response({'kind': kind, 'csv_url': url})


class HrSyncRosterView(APIView):
    """POST /api/employees/hr-sync-roster/ — hợp nhất roster từ các tab đã cấu hình & upsert."""

    def post(self, request):
        _require_data_admin(request)
        from .hr_import import sync_roster

        try:
            return Response(sync_roster(request.user.tenant))
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Đồng bộ roster thất bại: {exc}'}, status=400)


class HrSyncHistoryView(APIView):
    """POST /api/employees/hr-sync-history/ — nạp lịch sử (vị trí đã pass cấp S, khóa BQL,
    kết quả cấp O). Roster nên đồng bộ trước. Chỉ Admin/OM."""

    def post(self, request):
        _require_data_admin(request)
        from .hr_history import sync_history

        try:
            return Response(sync_history(request.user.tenant))
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Nạp lịch sử thất bại: {exc}'}, status=400)


class RecruitmentSyncNowView(APIView):
    """POST /api/employees/sync-now/ — kéo dữ liệu ngay từ link đã lưu (Cách 3)."""

    def post(self, request):
        _require_data_admin(request)
        from .models import RecruitmentSource
        from .recruitment import ingest_employees, load_rows_from_url

        src = RecruitmentSource.objects.filter(tenant=request.user.tenant).first()
        url = src.csv_url if src else ''
        if not url:
            return Response({'detail': 'Chưa cấu hình link CSV nguồn.'}, status=400)
        try:
            rows = load_rows_from_url(url)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Không đọc được nguồn: {exc}'}, status=400)
        return Response(ingest_employees(request.user.tenant, rows))


class RecruitmentImportFileView(APIView):
    """POST /api/employees/import-file/ (multipart, field 'file') — nhập từ Excel/CSV (Cách 2)."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        _require_data_admin(request)
        from .recruitment import ingest_employees, load_rows_from_upload

        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'Chưa chọn file.'}, status=400)
        try:
            rows = load_rows_from_upload(f)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Không đọc được file: {exc}'}, status=400)
        return Response(ingest_employees(request.user.tenant, rows))


class ExamHistoryImportView(APIView):
    """POST /api/employees/import-exam-history/ (multipart 'file') — nạp kết quả thi lịch sử (M4.1,
    mẫu 2). Chỉ Admin/OM."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        _require_data_admin(request)
        from .history_import import ingest_exam_history
        from .recruitment import load_rows_from_upload

        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'Chưa chọn file.'}, status=400)
        try:
            rows = load_rows_from_upload(f)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Không đọc được file: {exc}'}, status=400)
        return Response(ingest_exam_history(request.user.tenant, rows))


class EvaluationHistoryImportView(APIView):
    """POST /api/employees/import-eval-history/ (multipart 'file') — nạp đánh giá lịch sử (M4.1,
    mẫu 3). Chỉ Admin/OM."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        _require_data_admin(request)
        from .history_import import ingest_evaluation_history
        from .recruitment import load_rows_from_upload

        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'Chưa chọn file.'}, status=400)
        try:
            rows = load_rows_from_upload(f)
        except Exception as exc:  # noqa: BLE001
            return Response({'detail': f'Không đọc được file: {exc}'}, status=400)
        return Response(ingest_evaluation_history(request.user.tenant, rows))


class MgmtDevelopmentListView(APIView):
    """GET /api/employees/mgmt-development/ — danh sách phát triển Ban quản lý (cấp O): nội dung
    đã đào tạo, điểm thi theo vai, đánh giá, trạng thái sẵn sàng + số khóa/buổi đã tham gia."""

    def get(self, request):
        if (request.user.role or '').lower() not in {'admin', 'om', 'bod'}:
            return Response({'detail': 'Chỉ Admin/OM/BOD được xem danh sách Ban quản lý.'}, status=403)
        from .models import MgmtDevelopment

        tenant = request.user.tenant
        devs = MgmtDevelopment.objects.filter(tenant=tenant).select_related(
            'employee', 'employee__restaurant'
        )
        from sourcing.models import Attendance, Enrollment, Program

        prog = Program.objects.filter(tenant=tenant, name='Đào tạo Ban quản lý (lịch sử)').first()
        courses_by_emp, sessions_by_emp = {}, {}
        if prog:
            for eid in Enrollment.objects.filter(cohort__program=prog).values_list('employee_id', flat=True):
                courses_by_emp[eid] = courses_by_emp.get(eid, 0) + 1
            for eid in Attendance.objects.filter(
                session__cohort__program=prog, present=True
            ).values_list('enrollment__employee_id', flat=True):
                sessions_by_emp[eid] = sessions_by_emp.get(eid, 0) + 1

        rows = []
        for d in devs:
            e = d.employee
            rows.append({
                'employee_id': e.id, 'code': e.code, 'name': e.name,
                'position': e.position, 'job_level': e.job_level,
                'restaurant_name': e.restaurant.name if e.restaurant else '',
                'target_code': d.target_code, 'final_status': d.final_status, 'source': d.employee_source,
                'topics': d.data.get('topics', []), 'scores': d.data.get('scores', {}),
                'assessments': d.data.get('assessments', {}),
                'courses_attended': courses_by_emp.get(e.id, 0),
                'sessions_attended': sessions_by_emp.get(e.id, 0),
            })
        rows.sort(key=lambda r: (r['final_status'], r['name']))
        return Response(rows)


class DashboardStatsView(APIView):
    """GET /api/employees/dashboard/ — so lieu tong hop cho man Dashboard (Admin/Training/
    OM/BOD). Port Api.gs::api_dashboardStats. Khong gioi han role - moi role deu xem duoc
    (BOD chi xem, khong co thao tac ghi nao trong payload nay)."""


    def get(self, request):
        order = request.query_params.get('recent_order', 'oldest')
        status_filter = request.query_params.get('recent_status', 'all')
        return Response(dashboard_payload(request.user, recent_order=order, recent_status=status_filter))


class HomeStatsView(APIView):
    """GET /api/employees/home/ — so lieu ca nhan cho man Home (Trainer/BQL/AM/KCS). Port
    TrainingService.gs::listTrainees."""


    def get(self, request):
        return Response(home_payload(request.user))


class StudentDetailView(APIView):
    """GET /api/employees/<id>/detail/ — chi tiet hoc vien (thong tin + tien do + checklist +
    LMS + danh gia + hoi dong). Port EmployeeService.gs::getStudentDetail."""


    def get(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        # Tính lại kết quả thử việc theo điều kiện hiện tại (gồm đào tạo 100%) để luôn hiển thị
        # đúng, không phụ thuộc giá trị final_result cũ đã import.
        from .services import recompute_final_result

        recompute_final_result(employee)
        return Response(student_detail(employee))


class StudentChangeStatusView(APIView):
    """POST /api/employees/<id>/change-status/ — panel Quan tri nhan su, chi Admin/BQL. Port
    EmployeeService.gs::changeStatus (khong co state-machine, nhan bat ky gia tri hop le nao)."""


    def post(self, request, pk):
        if (request.user.role or '').lower() not in STUDENT_ADMIN_ROLES:
            return Response({'detail': 'Bạn không có quyền đổi trạng thái nhân sự.'}, status=403)
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        # BQL/Trainer chỉ được đổi trạng thái nhân sự thuộc nhà hàng mình phụ trách.
        from employees.permissions import get_restaurant_scope

        scope = get_restaurant_scope(request.user)
        if not scope['all'] and employee.restaurant_id not in scope['restaurant_ids']:
            return Response({'detail': 'Bạn không đủ quyền cập nhật nhân sự nhà hàng này.'}, status=403)
        new_status = request.data.get('employee_status')
        if new_status not in dict(Employee.EmployeeStatus.choices):
            return Response({'detail': 'Trạng thái không hợp lệ.'}, status=400)
        change_employee_status(employee, new_status)
        return Response(EmployeeSerializer(employee, context={'request': request}).data)


class StudentOfficeResultView(APIView):
    """POST /api/employees/<id>/office-result/ — ghi kết quả thử việc khối Văn phòng (Đạt/Không đạt).
    Kết hợp LMS học xong → tự chuyển Pass. Chỉ Admin/OM (Phòng Đào tạo)."""

    def post(self, request, pk):
        if (request.user.role or '').lower() not in {'admin', 'om'}:
            return Response({'detail': 'Chỉ Admin/OM (Phòng Đào tạo) được ghi kết quả.'}, status=403)
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        result = request.data.get('result')
        if result not in ('Đạt', 'Không đạt'):
            return Response({'detail': 'Kết quả không hợp lệ (Đạt / Không đạt).'}, status=400)
        employee.office_result = result
        employee.save(update_fields=['office_result'])
        from .services import recompute_final_result

        recompute_final_result(employee)
        return Response({'office_result': result, 'final_result': employee.final_result})


class LevelUpEligibleView(APIView):
    """GET /api/employees/levelup-eligible/ — danh sách theo dõi lộ trình (cấp S còn dưới S3) +
    trạng thái đủ điều kiện đăng ký. Theo phạm vi nhà hàng."""

    def get(self, request):
        from .career import levelup_eligible_list

        qs = Employee.objects.filter(
            tenant=request.user.tenant, level_group='S',
        ).exclude(employee_status=Employee.EmployeeStatus.RESIGNED).select_related('restaurant')
        from employees.permissions import get_restaurant_scope

        scope = get_restaurant_scope(request.user)
        if not scope['all']:
            qs = qs.filter(restaurant_id__in=scope['restaurant_ids'])
        return Response(levelup_eligible_list(list(qs)))


class LevelUpOptionsView(APIView):
    """GET /api/employees/<id>/levelup-options/ — dữ liệu cho BQL đăng ký thăng tiến (M1.2):
    level hiện tại/đích, khối FOH/BOH, vị trí đã đạt, cổng đăng ký + danh sách vị trí đích hợp lệ.
    BQL/Trainer chỉ xem nhân sự nhà hàng mình; Admin/OM toàn hệ thống."""

    def get(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        from employees.permissions import get_restaurant_scope

        scope = get_restaurant_scope(request.user)
        if not scope['all'] and employee.restaurant_id not in scope['restaurant_ids']:
            return Response({'detail': 'Bạn không đủ quyền xem nhân sự nhà hàng này.'}, status=403)
        from .career import levelup_options

        return Response(levelup_options(employee))


LEVELUP_REGISTER_ROLES = {'admin', 'om', 'bql'}
LEVELUP_OPEN_ROLES = {'admin', 'om', 'trainer'}


class ExamBatchListView(APIView):
    """GET /api/employees/exam-batches/ — các đợt thi còn mở đăng ký (T4/T8/T12, trước 1 tháng)."""

    def get(self, request):
        from .career import upcoming_exam_batches

        return Response(upcoming_exam_batches())


class LevelUpRegisterView(APIView):
    """POST /api/employees/<id>/levelup-register/ — BQL đăng ký nhân sự cho vị trí đích + đợt thi.
    Body: {target_position, exam_batch}. Chốt chặn 3 tháng + cùng khối + đợt hợp lệ ở server."""

    def post(self, request, pk):
        if (request.user.role or '').lower() not in LEVELUP_REGISTER_ROLES:
            return Response({'detail': 'Chỉ Admin/OM/BQL được đăng ký thăng tiến.'}, status=403)
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        from employees.permissions import get_restaurant_scope

        scope = get_restaurant_scope(request.user)
        if not scope['all'] and employee.restaurant_id not in scope['restaurant_ids']:
            return Response({'detail': 'Bạn không đủ quyền với nhân sự nhà hàng này.'}, status=403)
        from .career import register_levelup
        from .serializers import LevelUpEnrollmentSerializer

        enrollment, err = register_levelup(
            employee,
            request.data.get('target_position'),
            request.data.get('exam_batch'),
            request.user,
        )
        if err:
            return Response({'detail': err}, status=400)
        return Response(LevelUpEnrollmentSerializer(enrollment).data, status=201)


class LevelUpEnrollmentListView(APIView):
    """GET /api/employees/levelup-enrollments/ — danh sách đợt thăng tiến (theo phạm vi nhà hàng).
    Lọc tuỳ chọn: ?status= &exam_batch= &employee=."""

    def get(self, request):
        from .models import LevelUpEnrollment
        from .serializers import LevelUpEnrollmentSerializer

        qs = LevelUpEnrollment.objects.filter(tenant=request.user.tenant).select_related(
            'employee', 'employee__restaurant', 'registered_by'
        )
        from employees.permissions import get_restaurant_scope

        scope = get_restaurant_scope(request.user)
        if not scope['all']:
            qs = qs.filter(employee__restaurant_id__in=scope['restaurant_ids'])
        status_f = request.query_params.get('status')
        if status_f:
            qs = qs.filter(status=status_f)
        batch_f = request.query_params.get('exam_batch')
        if batch_f:
            qs = qs.filter(exam_batch=batch_f)
        emp_f = request.query_params.get('employee')
        if emp_f:
            qs = qs.filter(employee_id=emp_f)
        qs = qs.order_by('-created_at')
        return Response(LevelUpEnrollmentSerializer(qs, many=True).data)


class LevelUpOpenTrainingView(APIView):
    """POST /api/employees/levelup-enrollments/<id>/open-training/ — Phòng Đào tạo ghép khoá CLS
    xong → mở vòng đào tạo (Đăng ký → Đang đào tạo). Chỉ Admin/OM/Trainer."""

    def post(self, request, pk):
        if (request.user.role or '').lower() not in LEVELUP_OPEN_ROLES:
            return Response({'detail': 'Chỉ Admin/OM/Trainer được mở vòng đào tạo.'}, status=403)
        from .career import open_training
        from .models import LevelUpEnrollment
        from .serializers import LevelUpEnrollmentSerializer

        enrollment = get_object_or_404(LevelUpEnrollment, pk=pk, tenant=request.user.tenant)
        ok, err = open_training(enrollment)
        if not ok:
            return Response({'detail': err}, status=400)
        return Response(LevelUpEnrollmentSerializer(enrollment).data)


class LevelUpRoundView(APIView):
    """GET /api/employees/levelup-enrollments/<id>/round/ — dữ liệu 1 vòng thăng tiến (checklist
    vị trí đích + tiến độ + LMS/thi + đánh giá kỹ năng của vòng). Theo phạm vi nhà hàng."""

    def get(self, request, pk):
        from .career import levelup_round_detail
        from .models import LevelUpEnrollment

        enrollment = get_object_or_404(
            LevelUpEnrollment.objects.select_related('employee', 'employee__restaurant'),
            pk=pk, tenant=request.user.tenant,
        )
        from employees.permissions import get_restaurant_scope

        scope = get_restaurant_scope(request.user)
        if not scope['all'] and enrollment.employee.restaurant_id not in scope['restaurant_ids']:
            return Response({'detail': 'Bạn không đủ quyền xem vòng đào tạo này.'}, status=403)
        return Response(levelup_round_detail(enrollment))


class LevelUpEvaluateView(APIView):
    """POST /api/employees/levelup-enrollments/<id>/evaluate/ — chấm đánh giá vòng thăng tiến
    (Skill_BQL / AM_KCS) theo tiêu chí vị trí đích. Body giống phiếu đánh giá thường."""

    def post(self, request, pk):
        from evaluation.services import ValidationError as EvalValidationError, save_levelup_evaluation
        from .models import LevelUpEnrollment
        from evaluation.serializers import EvaluationSerializer

        enrollment = get_object_or_404(
            LevelUpEnrollment.objects.select_related('employee', 'employee__restaurant'),
            pk=pk, tenant=request.user.tenant,
        )
        from employees.permissions import get_restaurant_scope

        scope = get_restaurant_scope(request.user)
        if not scope['all'] and enrollment.employee.restaurant_id not in scope['restaurant_ids']:
            return Response({'detail': 'Bạn không đủ quyền đánh giá vòng này.'}, status=403)
        try:
            evaluation = save_levelup_evaluation(request.user, enrollment, request.data)
        except EvalValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(EvaluationSerializer(evaluation).data, status=200)


LEVELUP_DECIDE_ROLES = {'admin', 'om'}


class LevelUpCompleteView(APIView):
    """POST /api/employees/levelup-enrollments/<id>/complete/ — Phòng Đào tạo chốt lên level nếu đủ
    điều kiện (LMS 100% + thi đạt + checklist 100% + điểm tổng 40/60 ≥85%). Chỉ Admin/OM."""

    def post(self, request, pk):
        if (request.user.role or '').lower() not in LEVELUP_DECIDE_ROLES:
            return Response({'detail': 'Chỉ Admin/OM (Phòng Đào tạo) được chốt lên level.'}, status=403)
        from .career import complete_levelup
        from .models import LevelUpEnrollment

        enrollment = get_object_or_404(LevelUpEnrollment, pk=pk, tenant=request.user.tenant)
        result, err = complete_levelup(enrollment, request.user)
        if err:
            return Response({'detail': err}, status=400)
        return Response(result)


class LevelUpFailView(APIView):
    """POST /api/employees/levelup-enrollments/<id>/fail/ — đánh dấu vòng không đạt. Chỉ Admin/OM."""

    def post(self, request, pk):
        if (request.user.role or '').lower() not in LEVELUP_DECIDE_ROLES:
            return Response({'detail': 'Chỉ Admin/OM được đánh dấu không đạt.'}, status=403)
        from .career import fail_levelup
        from .models import LevelUpEnrollment
        from .serializers import LevelUpEnrollmentSerializer

        enrollment = get_object_or_404(LevelUpEnrollment, pk=pk, tenant=request.user.tenant)
        ok, err = fail_levelup(enrollment, request.user)
        if not ok:
            return Response({'detail': err}, status=400)
        return Response(LevelUpEnrollmentSerializer(enrollment).data)


TALENT_REVIEW_ROLES = {'admin', 'om', 'am', 'kcs'}


class TalentPoolListView(APIView):
    """GET /api/employees/talent-pool/ — nhân sự nguồn CHÍNH THỨC (đủ 3 vị trí + AM/KCS đã duyệt)."""

    def get(self, request):
        if (request.user.role or '').lower() not in LEVELUP_DECIDE_ROLES:
            return Response({'detail': 'Chỉ Admin/OM được xem danh sách nhân sự nguồn.'}, status=403)
        from .career import achieved_positions, major_level, talent_pool_employees

        rows = [
            {
                'id': e.id, 'code': e.code, 'name': e.name,
                'restaurant_name': e.restaurant.name if e.restaurant else '',
                'level': major_level(e.job_level),
                'achieved_positions': achieved_positions(e),
            }
            for e in talent_pool_employees(request.user.tenant)
        ]
        return Response(rows)


class TalentCandidateListView(APIView):
    """GET /api/employees/talent-candidates/ — ứng viên nguồn (đủ 3 vị trí) + trạng thái đánh giá
    sẵn sàng của AM/KCS (G3). Admin/OM/AM/KCS."""

    def get(self, request):
        if (request.user.role or '').lower() not in TALENT_REVIEW_ROLES:
            return Response({'detail': 'Bạn không có quyền xem danh sách ứng viên nguồn.'}, status=403)
        from .career import achieved_positions, major_level, talent_candidates

        rows = []
        for c in talent_candidates(request.user.tenant):
            e = c['employee']
            rows.append({
                'id': e.id, 'code': e.code, 'name': e.name,
                'restaurant_name': e.restaurant.name if e.restaurant else '',
                'position': e.position, 'level': major_level(e.job_level),
                'positions_count': c['positions_count'],
                'achieved_positions': achieved_positions(e),
                'decision': c['decision'], 'note': c['note'], 'reviewed_by': c['reviewed_by'],
            })
        return Response(rows)


class TalentReviewView(APIView):
    """POST /api/employees/<id>/talent-review/ — AM/KCS/Admin đánh giá sẵn sàng: {decision, note}.
    decision = approved (vào nguồn) / rejected (chưa sẵn sàng)."""

    def post(self, request, pk):
        if (request.user.role or '').lower() not in TALENT_REVIEW_ROLES:
            return Response({'detail': 'Chỉ AM/KCS/Admin/OM được đánh giá sẵn sàng.'}, status=403)
        from django.utils import timezone

        from .models import TalentReview

        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        decision = request.data.get('decision')
        if decision not in ('approved', 'rejected'):
            return Response({'detail': 'Quyết định không hợp lệ (approved / rejected).'}, status=400)
        TalentReview.objects.update_or_create(
            tenant=request.user.tenant, employee=employee,
            defaults={
                'decision': decision, 'note': request.data.get('note', '') or '',
                'reviewed_by': request.user, 'reviewed_at': timezone.now(),
            },
        )
        return Response({'decision': decision})


class StudentExportProbationResultView(APIView):
    """POST /api/employees/<id>/export-probation-result/ — xuat phieu ket qua thu viec PDF,
    chi Admin/BQL va chi khi final_result la 'Pass thu viec' (enforce server-side, chat hon
    ban goc vi ban goc chi an nut o client)."""


    def post(self, request, pk):
        if (request.user.role or '').lower() not in STUDENT_ADMIN_ROLES:
            return Response({'detail': 'Bạn không có quyền xuất phiếu kết quả thử việc.'}, status=403)
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        if not (employee.final_result or '').startswith('Pass'):
            return Response({'detail': 'Chỉ xuất phiếu khi nhân sự đã Đạt thử việc.'}, status=400)
        pdf_url = export_probation_result_pdf(employee)
        return Response({'pdf_url': pdf_url})
