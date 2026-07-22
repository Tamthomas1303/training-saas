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
    filterset_fields = ['restaurant', 'employee_status', 'operation_unit', 'level_group']
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
