from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination
from employees.models import Employee
from employees.serializers import EmployeeSerializer

from .models import Checklist, TrainingProgress
from .pdf import build_training_record_pdf
from .serializers import ChecklistSerializer, TrainingProgressSerializer
from .storage import StorageError, is_data_url, upload_data_url, upload_pdf_bytes

REQUIRED_FIELDS_FOR_COMPLETE = (
    'img_tailieu', 'img_lythuyet', 'img_thuchanh', 'sign_trainer', 'sign_trainee',
)


class ChecklistViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ChecklistSerializer
    queryset = Checklist.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['brand', 'position', 'level_group', 'category']
    search_fields = ['task_name', 'description']
    ordering_fields = ['order', 'day']
    ordering = ['order']


def _normalize_key(value):
    return (value or '').strip().lower()


class EmployeeChecklistView(APIView):
    """GET /api/checklist/training/?employee=<id> — checklist theo Brand+Position cua nhan su,
    ghep voi TrainingProgress hien co (neu co). Khoa loc giong het EmployeeService.gs::_checklistFor
    trong ban Apps Script cu (chi Brand + Position, khong dung Level_Group)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee_id = request.query_params.get('employee')
        if not employee_id:
            return Response({'detail': 'Thiếu tham số employee'}, status=400)

        employee = get_object_or_404(Employee, pk=employee_id, tenant=request.user.tenant)
        employee_data = EmployeeSerializer(employee, context={'request': request}).data

        if not employee.restaurant:
            return Response({'employee': employee_data, 'items': []})

        brand = employee.restaurant.brand
        position_key = _normalize_key(employee.position)

        checklists = [
            c for c in Checklist.objects.filter(tenant=request.user.tenant, brand=brand).order_by('day', 'order')
            if _normalize_key(c.position) == position_key
        ]

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

    Port logic tu TrainingService.gs::saveProgress: hoan thanh (complete=true) bat buoc phai
    co du 3 anh (img_tailieu/img_lythuyet/img_thuchanh) + 2 chu ky (sign_trainer/sign_trainee),
    khac thi bao loi. Luu nhap (complete=false) khong yeu cau gi, cho phep luu tung phan.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        tenant = request.user.tenant
        employee_id = request.data.get('employee')
        checklist_id = request.data.get('checklist')
        if not employee_id or not checklist_id:
            return Response({'detail': 'Thiếu employee hoặc checklist'}, status=400)

        employee = get_object_or_404(Employee, pk=employee_id, tenant=tenant)
        checklist = get_object_or_404(Checklist, pk=checklist_id, tenant=tenant)

        progress, _ = TrainingProgress.objects.get_or_create(
            tenant=tenant, employee=employee, checklist=checklist,
        )

        folder_for_field = {
            'img_tailieu': f'evidence/{tenant.id}/{employee.id}',
            'img_lythuyet': f'evidence/{tenant.id}/{employee.id}',
            'img_thuchanh': f'evidence/{tenant.id}/{employee.id}',
            'sign_trainer': f'signatures/{tenant.id}',
            'sign_trainee': f'signatures/{tenant.id}',
        }

        for field, folder in folder_for_field.items():
            value = request.data.get(field)
            if not value:
                continue  # rong -> giu nguyen gia tri cu (luu tung phan)
            if is_data_url(value):
                try:
                    url = upload_data_url(value, folder, f'{field}_{checklist.id}')
                except StorageError as exc:
                    return Response({'detail': str(exc)}, status=400)
                setattr(progress, field, url)
            else:
                setattr(progress, field, value)  # da la URL san co tu lan luu truoc

        note = request.data.get('note')
        if note is not None:
            progress.note = note

        want_complete = bool(request.data.get('complete'))
        has_all = all(getattr(progress, f) for f in REQUIRED_FIELDS_FOR_COMPLETE)

        if want_complete and not has_all:
            return Response(
                {
                    'detail': (
                        'Cần đủ 3 ảnh (tài liệu, lý thuyết, thực hành) và 2 chữ ký '
                        '(trainer + học viên) để hoàn thành.'
                    )
                },
                status=400,
            )

        progress.trainer = request.user
        progress.status = (
            TrainingProgress.Status.DONE if want_complete else TrainingProgress.Status.IN_PROGRESS
        )

        if want_complete:
            progress.completed_at = timezone.now()
            pdf_bytes = build_training_record_pdf(_build_pdf_context(employee, checklist, progress, request.user))
            try:
                pdf_url = upload_pdf_bytes(
                    pdf_bytes, f'bienban/{tenant.id}', f'BienBan_{employee.id}_{checklist.id}'
                )
            except StorageError as exc:
                return Response({'detail': str(exc)}, status=400)
            progress.pdf_url = pdf_url

        progress.save()

        return Response(TrainingProgressSerializer(progress).data)


def _build_pdf_context(employee, checklist, progress, user):
    return {
        'record_no': f'{progress.id}/{timezone.now().year}',
        'tenant_name': employee.tenant.name,
        'employee': {
            'name': employee.name,
            'position': employee.position,
            'restaurant': employee.restaurant.name if employee.restaurant else '',
            'start_date': employee.start_date.strftime('%d/%m/%Y') if employee.start_date else '',
        },
        'item': {
            'name': checklist.task_name,
            'category': checklist.category,
            'train_date': timezone.now().strftime('%d/%m/%Y'),
        },
        'trainer_name': user.full_name or user.username,
        'note': progress.note,
        'images': {
            'tai_lieu': progress.img_tailieu,
            'ly_thuyet': progress.img_lythuyet,
            'thuc_hanh': progress.img_thuchanh,
        },
        'sign_trainer_url': progress.sign_trainer,
        'sign_trainee_url': progress.sign_trainee,
    }
