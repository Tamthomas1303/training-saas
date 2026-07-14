import datetime

FINAL_RESULT_CUTOFF_DATE = datetime.date(2026, 4, 6)


def normalize_key(value):
    return (value or '').strip().lower()


def matching_checklist_items(employee):
    """Checklist cua 1 nhan su, khop theo Brand (tu restaurant) + Position (normalized).

    Port EmployeeService.gs::_checklistFor - chi Brand + Position, KHONG dung Level_Group
    (giu dung logic ban Apps Script cu).
    """
    from checklist.models import Checklist  # import tre de tranh vong lap luc nap app

    if not employee.restaurant:
        return []
    brand = employee.restaurant.brand
    position_key = normalize_key(employee.position)
    return [
        c for c in Checklist.objects.filter(tenant=employee.tenant, brand=brand).order_by('day', 'order')
        if normalize_key(c.position) == position_key
    ]


def checklist_progress_percent(employee):
    """% tien do dao tao = so checklist da Hoan thanh / tong so checklist khop brand+position."""
    from checklist.models import TrainingProgress

    items = matching_checklist_items(employee)
    if not items:
        return 0
    done_count = TrainingProgress.objects.filter(
        employee=employee,
        checklist_id__in=[c.id for c in items],
        status=TrainingProgress.Status.DONE,
    ).count()
    return round(done_count / len(items) * 100)


def lms_done(employee):
    """Port ProbationService.gs::_lmsDone. Ban goc kiem tra Progress_Status>=100 tren
    DB_KetQuaHoc; he thong nay khong luu progress so, chi luu status Dat/Chua dat sau khi
    sync_cls xu ly - nen dung status='Đạt' lam dieu kien tuong duong."""
    from cls_sync.models import CourseResult

    return CourseResult.objects.filter(employee=employee, status='Đạt').exists()


def exam_pass(employee, threshold=None):
    """Port ProbationService.gs::_examPass (Config.examPass(), mac dinh 80)."""
    from django.conf import settings

    from cls_sync.models import ExamResult

    threshold = settings.COMMISSION_EXAM_THRESHOLD if threshold is None else threshold
    return ExamResult.objects.filter(employee=employee, passed=True, score__gte=threshold).exists()


def latest_skill_eval_percent(employee):
    """% cua lan danh gia ky nang BQL (Skill_BQL) gan nhat da Hoan thanh."""
    from evaluation.models import Evaluation

    ev = (
        Evaluation.objects.filter(employee=employee, eval_type='Skill_BQL', status='done')
        .order_by('-completed_at')
        .first()
    )
    return float(ev.percent) if ev else None


def worked_days(employee):
    from django.utils import timezone

    if not employee.start_date:
        return None
    return (timezone.now().date() - employee.start_date).days


def trainer_of(employee):
    """Port CommissionService.gs::_trainerOf - uu tien Employee.trainer, fallback trainer
    da ghi nhan tren checklist dao tao (TrainingProgress.trainer)."""
    if employee.trainer_id:
        return employee.trainer
    from checklist.models import TrainingProgress

    progress = TrainingProgress.objects.filter(employee=employee, trainer__isnull=False).first()
    return progress.trainer if progress else None


def best_exam_score(employee):
    from cls_sync.models import ExamResult

    best = (
        ExamResult.objects.filter(employee=employee, score__isnull=False)
        .order_by('-score')
        .first()
    )
    return float(best.score) if best else 0


def compute_final_result(employee):
    """Ket qua thu viec (cot T). Port ProbationService.gs::computeFinalResult, phan theo
    Operation_Unit/Job_Position dung y ban goc. Don gian hoa 2 diem (theo quyet dinh khi lam
    ĐỢT 2 - "cong thuc thu viec"): 'eligible' (du DK thi) dung lms_done() thay vi diem khoa
    'Hoi nhap' rieng; 'theory' dung diem thi cao nhat cua NV (khong tach lan 1/lan 2-3)."""
    from .models import Employee

    if employee.employee_status == Employee.EmployeeStatus.RESIGNED:
        return 'Đã nghỉ việc'

    position = (employee.position or '').lower()
    unit = employee.operation_unit
    eligible = lms_done(employee)

    if unit == Employee.OperationUnit.PRODUCTION:
        return 'Pass thử việc'

    if unit == Employee.OperationUnit.OFFICE:
        return 'Pass thử việc' if (eligible and employee.office_result == 'Đạt') else 'Tiếp tục thử việc'

    is_bep_truong_pho = 'bếp trưởng' in position or 'bếp phó' in position
    is_quan_ly_giam_sat = 'quản lý' in position or 'giám sát' in position

    if is_bep_truong_pho:
        ok = eligible and exam_pass(employee) and employee.skill_result == 'Đạt' and employee.shift_ops == 'Đạt'
        return 'Pass thử việc' if ok else 'Tiếp tục thử việc'

    if is_quan_ly_giam_sat:
        ok = eligible and exam_pass(employee) and employee.shift_ops == 'Đạt'
        return 'Pass thử việc' if ok else 'Tiếp tục thử việc'

    # Nhan vien thuong (cap S)
    if not eligible:
        return 'Tiếp tục thử việc'
    theory = best_exam_score(employee)
    skill_percent = float(employee.skill_score) * 100 if employee.skill_score is not None else 0
    weighted = theory * 0.4 + skill_percent * 0.6
    if employee.start_date and employee.start_date < FINAL_RESULT_CUTOFF_DATE:
        return 'Pass thử việc' if weighted >= 80 else 'Tiếp tục thử việc'
    return 'Pass thử việc' if (weighted >= 80 and exam_pass(employee)) else 'Tiếp tục thử việc'


def recompute_final_result(employee):
    employee.final_result = compute_final_result(employee)
    employee.save(update_fields=['final_result'])
    return employee.final_result


def change_employee_status(employee, new_status):
    """Doi trang thai lam viec cua nhan su + tinh lai ket qua thu viec. Port
    EmployeeService.gs::changeStatus (khong co state-machine kiem tra chuyen trang thai,
    giong ban goc)."""
    employee.employee_status = new_status
    employee.save(update_fields=['employee_status'])
    return recompute_final_result(employee)


def probation_conditions(employee):
    """5 dieu kien hoa hong trainer. Port ProbationService.gs::getConditions (chi phan
    lien quan hoa hong: khong tinh final_result/computeFinalResult - thuoc sprint khac)."""
    from django.conf import settings

    lms = lms_done(employee)
    exam = exam_pass(employee)
    training = checklist_progress_percent(employee) >= 100
    skill_percent = latest_skill_eval_percent(employee)
    skill_pass = skill_percent is not None and skill_percent >= settings.COMMISSION_SKILL_THRESHOLD
    days = worked_days(employee)
    worked_1month = days is not None and days >= settings.COMMISSION_WORKED_DAYS

    return {
        'lms': lms,
        'exam': exam,
        'training': training,
        'skill_percent': skill_percent,
        'skill_pass': skill_pass,
        'worked_days': days,
        'worked_1month': worked_1month,
        'all_pass': lms and exam and training and skill_pass,
    }
