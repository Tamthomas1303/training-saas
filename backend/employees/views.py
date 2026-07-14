from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
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


class EmployeeViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.select_related('restaurant', 'trainer').all()
    pagination_class = DefaultPagination
    filterset_fields = ['restaurant', 'employee_status', 'operation_unit', 'level_group']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'start_date']
    ordering = ['name']


class DashboardStatsView(APIView):
    """GET /api/employees/dashboard/ — so lieu tong hop cho man Dashboard (Admin/Training/
    OM/BOD). Port Api.gs::api_dashboardStats. Khong gioi han role - moi role deu xem duoc
    (BOD chi xem, khong co thao tac ghi nao trong payload nay)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(dashboard_payload(request.user))


class HomeStatsView(APIView):
    """GET /api/employees/home/ — so lieu ca nhan cho man Home (Trainer/BQL/AM/KCS). Port
    TrainingService.gs::listTrainees."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(home_payload(request.user))


class StudentDetailView(APIView):
    """GET /api/employees/<id>/detail/ — chi tiet hoc vien (thong tin + tien do + checklist +
    LMS + danh gia + hoi dong). Port EmployeeService.gs::getStudentDetail."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        return Response(student_detail(employee))


class StudentChangeStatusView(APIView):
    """POST /api/employees/<id>/change-status/ — panel Quan tri nhan su, chi Admin/BQL. Port
    EmployeeService.gs::changeStatus (khong co state-machine, nhan bat ky gia tri hop le nao)."""

    permission_classes = [IsAuthenticated]

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

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if (request.user.role or '').lower() not in STUDENT_ADMIN_ROLES:
            return Response({'detail': 'Bạn không có quyền xuất phiếu kết quả thử việc.'}, status=403)
        employee = get_object_or_404(Employee, pk=pk, tenant=request.user.tenant)
        if not (employee.final_result or '').startswith('Pass'):
            return Response({'detail': 'Chỉ xuất phiếu khi nhân sự đã Đạt thử việc.'}, status=400)
        pdf_url = export_probation_result_pdf(employee)
        return Response({'pdf_url': pdf_url})
