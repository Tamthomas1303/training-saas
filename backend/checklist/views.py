from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
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

    @action(detail=False, methods=['post'], url_path='bulk-assign-competency')
    def bulk_assign_competency(self, request):
        """POST /api/checklist/bulk-assign-competency/ {ids: [...]} HOẶC {category: 'X'} +
        {competency: <id hoặc null>} - gán 1 năng lực cho NHIỀU dòng checklist cùng lúc (theo
        chọn tay hoặc theo cả 1 nhóm/category), thay vì phải sửa từng dòng (Prompt_Dashboard_
        A1_GanNhanNangLuc.md, mục 1)."""
        ids = request.data.get('ids')
        category = (request.data.get('category') or '').strip()
        if not ids and not category:
            return Response({'detail': "Cần 'ids' (danh sách id) hoặc 'category' (tên nhóm)."}, status=400)

        competency_id = request.data.get('competency') or None
        if competency_id is not None:
            from dashboard.models import Competency

            if not Competency.objects.filter(tenant=request.user.tenant, pk=competency_id).exists():
                return Response({'detail': 'Năng lực không hợp lệ.'}, status=400)

        qs = Checklist.objects.filter(tenant=request.user.tenant)
        qs = qs.filter(id__in=ids) if ids else qs.filter(category=category)
        updated = qs.update(competency_id=competency_id)
        return Response({'updated': updated})

    @action(detail=False, methods=['post'], url_path='bulk-assign-phase')
    def bulk_assign_phase(self, request):
        """POST /api/checklist/bulk-assign-phase/ {ids: [...]} HOAC {category: 'X'} +
        {phase: 'core'|'completion'} - gan phase cho NHIEU dong checklist cung luc (Khung noi
        dung cap S - Buoc 2, Prompt_KhungNoiDung_CapS_Buoc2.md muc 1), cung mau voi
        bulk-assign-competency o tren."""
        ids = request.data.get('ids')
        category = (request.data.get('category') or '').strip()
        if not ids and not category:
            return Response({'detail': "Cần 'ids' (danh sách id) hoặc 'category' (tên nhóm)."}, status=400)

        phase = request.data.get('phase')
        if phase not in dict(Checklist.Phase.choices):
            return Response({'detail': "'phase' phải là 'core' hoặc 'completion'."}, status=400)

        qs = Checklist.objects.filter(tenant=request.user.tenant)
        qs = qs.filter(id__in=ids) if ids else qs.filter(category=category)
        updated = qs.update(phase=phase)
        return Response({'updated': updated})


class DocumentViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD tai lieu - man 5.8. Doc: moi role dang nhap. Ghi (them/sua/xoa): chi Admin. Port
    DocumentService.gs::upsert (requireRole Admin/Training)."""

    serializer_class = DocumentSerializer
    queryset = Document.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['brand', 'status']
    search_fields = ['name', 'code']
    ordering_fields = ['name', 'uploaded_at']
    ordering = ['name']

    def get_queryset(self):
        qs = super().get_queryset()
        # Tài liệu dùng cho NHIỀU vị trí (chuỗi ';'). Lọc theo 1 vị trí = khớp thành viên; tài
        # liệu để trống vị trí = dùng chung mọi vị trí nên luôn hiển thị.
        position = self.request.query_params.get('position')
        if position:
            from django.db.models import Q

            qs = qs.filter(Q(position__icontains=position) | Q(position=''))
        return qs

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

        # M1.6: cho phép đào tạo checklist của MỘT vị trí khác (vị trí đích khi thăng tiến).
        # Mặc định = vị trí hiện tại (onboarding).
        position = request.query_params.get('position') or None
        checklists = matching_checklist_items(employee, position)

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
