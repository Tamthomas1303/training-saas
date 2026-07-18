from django.utils import timezone

from employees.models import Employee
from employees.permissions import can_train_position

from .models import Checklist, TrainingProgress
from .pdf import build_training_record_pdf
from .storage import StorageError, is_data_url, upload_data_url, upload_pdf_bytes

REQUIRED_FIELDS_FOR_COMPLETE = (
    'img_tailieu', 'img_lythuyet', 'img_thuchanh', 'sign_trainer', 'sign_trainee',
)


class ValidationError(Exception):
    pass


def save_training_progress(user, payload):
    """Luu (nhap hoac hoan thanh) 1 dong TrainingProgress. Dung chung boi
    TrainingProgressSaveView (API truc tiep) va SyncDraftsView (hang doi offline).
    Nem ValidationError voi thong diep tieng Viet neu khong hop le.
    """
    tenant = user.tenant
    employee_id = payload.get('employee')
    checklist_id = payload.get('checklist')
    if not employee_id or not checklist_id:
        raise ValidationError('Thiếu employee hoặc checklist')

    employee = Employee.objects.filter(pk=employee_id, tenant=tenant).first()
    if not employee:
        raise ValidationError('Không tìm thấy nhân sự')
    checklist = Checklist.objects.filter(pk=checklist_id, tenant=tenant).first()
    if not checklist:
        raise ValidationError('Không tìm thấy checklist')

    if not can_train_position(user, employee.position):
        raise ValidationError('Bạn không có quyền đào tạo vị trí này.')

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
        value = payload.get(field)
        if not value:
            continue
        if is_data_url(value):
            try:
                url = upload_data_url(value, folder, f'{field}_{checklist.id}')
            except StorageError as exc:
                raise ValidationError(str(exc)) from exc
            setattr(progress, field, url)
        else:
            setattr(progress, field, value)

    note = payload.get('note')
    if note is not None:
        progress.note = note

    want_complete = bool(payload.get('complete'))
    has_all = all(getattr(progress, f) for f in REQUIRED_FIELDS_FOR_COMPLETE)

    if want_complete and not has_all:
        raise ValidationError(
            'Cần đủ 3 ảnh (tài liệu, lý thuyết, thực hành) và 2 chữ ký (trainer + học viên) để hoàn thành.'
        )

    progress.trainer = user
    progress.status = (
        TrainingProgress.Status.DONE if want_complete else TrainingProgress.Status.IN_PROGRESS
    )

    if want_complete:
        progress.completed_at = timezone.now()
        pdf_bytes = build_training_record_pdf(_build_pdf_context(employee, checklist, progress, user))
        try:
            pdf_url = upload_pdf_bytes(
                pdf_bytes, f'bienban/{tenant.id}', f'BienBan_{employee.id}_{checklist.id}'
            )
        except StorageError as exc:
            raise ValidationError(str(exc)) from exc
        progress.pdf_url = pdf_url

    progress.save()

    # Tiến độ đào tạo thay đổi → tính lại kết quả thử việc (điều kiện pass gồm đào tạo 100%).
    from employees.services import recompute_final_result

    recompute_final_result(employee)
    return progress


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
