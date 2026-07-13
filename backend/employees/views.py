from rest_framework import viewsets

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination

from .models import Employee
from .serializers import EmployeeSerializer


class EmployeeViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = EmployeeSerializer
    queryset = Employee.objects.select_related('restaurant', 'trainer').all()
    pagination_class = DefaultPagination
    filterset_fields = ['restaurant', 'employee_status', 'operation_unit', 'level_group']
    search_fields = ['code', 'name']
    ordering_fields = ['code', 'name', 'start_date']
    ordering = ['name']
