from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination
from employees.models import Employee
from employees.serializers import EmployeeSerializer
from employees.services import matching_checklist_items

from .models import Checklist, Document, TrainingProgress
from .serializers import ChecklistSerializer, DocumentSerializer, TrainingProgressSerializer
from .services import ValidationError, save_training_progress


class ChecklistViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD checklist dao tao. Doc: moi role dang nhap. Ghi (them/sua/xoa): chi Admin - dung
    quy uoc voi Document/Restaurant/User trong he thong nay."""

    serializer_class = ChecklistSerializer
    queryset = Checklist.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['brand', 'position', 'level_group', 'category']
    search_fields = ['task_name', 'description']
    ordering_fields = ['order', 'day']
    ordering = ['order']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and (request.user.role or '').lower() != 'admin':
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Chỉ Admin được thêm/sửa/xóa checklist.')


class DocumentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD tai lieu - man 5.8. Doc: moi role dang nhap. Ghi (them/sua/xoa): chi Admin. Port
    DocumentService.gs::upsert (requireRole Admin/Training)."""

    serializer_class = DocumentSerializer
    queryset = Document.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['brand', 'position', 'status']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'uploaded_at']
    ordering = ['name']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and (request.user.role or '').lower() != 'admin':
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Chỉ Admin được thêm/sửa/xóa tài liệu.')


class EmployeeChecklistView(APIView):
    """GET /api/checklist/training/?employee=<id> — checklist theo Brand+Position cua nhan su,
    ghep voi TrainingProgress hien co (neu co). Khoa loc giong het EmployeeService.gs::_checklistFor
    trong ban Apps Script cu (chi Brand + Position, khong dung Level_Group)."""


    def get(self, request):
        employee_id = request.query_params.get('employee')
        if not employee_id:
            return Response({'detail': 'Thiếu tham số employee'}, status=400)

        employee = get_object_or_404(Employee, pk=employee_id, tenant=request.user.tenant)
        employee_data = EmployeeSerializer(employee, context={'request': request}).data

        checklists = matching_checklist_items(employee)

        progress_by_checklist = {
            p.checklist_id: p
            for p in TrainingProgress.objects.filter(employee=employee).select_related('trainer')
        }

        items = [
            {
                'checklist': ChecklistSerializer(checklist).data,
                'progress': (
                    TrainingProgressSerializer(progress_by_checklist[checklist.id]).data
                    if checklist.id in progress_by_checklist else None
                ),
            }
            for checklist in checklists
        ]

        return Response({'employee': employee_data, 'items': items})


class TrainingProgressSaveView(APIView):
    """POST /api/checklist/training/save/ — luu (nhap hoac hoan thanh) 1 dong TrainingProgress.

    Logic thuc su nam o checklist/services.py::save_training_progress (dung chung voi
    hang doi offline SyncDraftsView).
    """


    def post(self, request):
        try:
            progress = save_training_progress(request.user, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(TrainingProgressSerializer(progress).data)
