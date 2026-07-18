from django.shortcuts import get_object_or_404
from rest_framework import viewsets
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

STUDENT_ADMIN_ROLES = {'admin', 'bql'}


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
        return Response(student_detail(employee))


class StudentChangeStatusView(APIView):
    """POST /api/employees/<id>/change-status/ — panel Quan tri nhan su, chi Admin/BQL. Port
    EmployeeService.gs::changeStatus (khong co state-machine, nhan bat ky gia tri hop le nao)."""


    def post(self, request, pk):
        if (request.user.role or '').lower() not in STUDENT_ADMIN_ROLES:
            return Response({'detail': 'Bạn không có quyền đổi trạng thái nhân sự.'}, status=403)
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        new_status = request.data.get('employee_status')
        if new_status not in dict(Employee.EmployeeStatus.choices):
            return Response({'detail': 'Trạng thái không hợp lệ.'}, status=400)
        change_employee_status(employee, new_status)
        return Response(EmployeeSerializer(employee, context={'request': request}).data)


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
