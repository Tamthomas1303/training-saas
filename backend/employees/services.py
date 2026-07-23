import datetime

FINAL_RESULT_CUTOFF_DATE = datetime.date(2026, 4, 6)


def normalize_key(value):
    return (value or '').strip().lower()


# Port EmployeeService.gs::BRAND_CODE + _brandCode — brand nhà hàng (tên đầy đủ) ↔ mã brand
# dùng trong sheet checklist. Khớp cả 2 chiều để không phụ thuộc kiểu lưu của dữ liệu import.
BRAND_CODE = {'Kampong': 'KMP', 'Yiam Yiam': 'YYM', 'Phở': 'PHO', 'Chilicious': 'CLS'}


def brand_code(brand_name):
    return BRAND_CODE.get((brand_name or '').strip(), brand_name)


def _brand_keys(brand_name):
    """Tập khóa brand để so khớp (chấp nhận cả tên đầy đủ lẫn mã)."""
    return {normalize_key(brand_name), normalize_key(brand_code(brand_name))}


def checklist_position(job_position):
    """Port EmployeeService.gs::_checklistPosition — rút vị trí công việc ('NV Phục vụ',
    'Tổ trưởng Phục vụ'...) về vị trí lõi khớp với sheet checklist ('Phục vụ'...).
    Bỏ qua tiền tố (NV/Tổ trưởng...), khớp theo chuỗi lõi."""
    p = normalize_key(job_position)
    if 'food check' in p:
        return 'Food check'
    if 'thớt' in p:
        return 'Bếp thớt'
    if 'salad' in p:
        return 'Bếp salad'
    if 'chảo' in p:
        return 'Bếp chảo'
    if 'cơm gà' in p:
        return 'Bếp cơm gà'
    if 'bể' in p or 'hải sản' in p:
        return 'Chăm sóc bể hải sản'
    if 'phục vụ' in p:
        return 'Phục vụ'
    if 'thu ngân' in p:
        return 'Thu ngân'
    if 'pha chế' in p or 'bar' in p:
        return 'Pha chế'
    if 'runner' in p:
        return 'Food runner'
    if 'phụ bếp' in p:
        return 'Bếp thớt'  # mặc định phụ bếp khởi đầu ở thớt
    return job_position


def matching_checklist_items(employee, position=None):
    """Checklist cua 1 nhan su, khop theo Brand (tu restaurant) + Position (normalized).

    Port EmployeeService.gs::_checklistFor - chi Brand + Position, KHONG dung Level_Group
    (giu dung logic ban Apps Script cu).

    position=None -> dung vi tri hien tai cua nhan su (onboarding). Truyen position khac (vd vi
    tri dich khi thang tien - M1.4) de lay checklist cua vi tri do, dung lai cung engine.
    """
    from checklist.models import Checklist  # import tre de tranh vong lap luc nap app

    if not employee.restaurant:
        return []
    brand_keys = _brand_keys(employee.restaurant.brand)
    pos = employee.position if position is None else position
    position_key = normalize_key(checklist_position(pos))
    return [
        c for c in Checklist.objects.filter(tenant=employee.tenant).order_by('day', 'order')
        if normalize_key(c.brand) in brand_keys and normalize_key(c.position) == position_key
    ]


def checklist_progress_percent(employee, position=None):
    """% tien do dao tao = so checklist da Hoan thanh / tong so checklist khop brand+position.
    position=None -> vi tri hien tai; truyen vi tri dich de tinh tien do vong thang tien (M1.4)."""
    from checklist.models import TrainingProgress

    items = matching_checklist_items(employee, position)
    if not items:
        return 0
    done_count = TrainingProgress.objects.filter(
        employee=employee,
        checklist_id__in=[c.id for c in items],
        status=TrainingProgress.Status.DONE,
    ).count()
    return round(done_count / len(items) * 100)


def batch_checklist_progress_percent(employees):
    """Nhu checklist_progress_percent nhung tinh cho nhieu nhan su cung luc bang vai truy
    van co dinh (thay vi ~2 truy van/nhan su) - tranh N+1 khi liet ke danh sach nhan su."""
    from collections import defaultdict

    from checklist.models import Checklist, TrainingProgress

    employees = list(employees)
    if not employees:
        return {}

    tenant = employees[0].tenant
    by_brand_position = defaultdict(list)
    for c in Checklist.objects.filter(tenant=tenant):
        by_brand_position[(normalize_key(c.brand), normalize_key(c.position))].append(c)

    items_by_employee = {}
    all_checklist_ids = set()
    for e in employees:
        items = []
        if e.restaurant:
            pos_key = normalize_key(checklist_position(e.position))
            for bk in _brand_keys(e.restaurant.brand):
                items.extend(by_brand_position.get((bk, pos_key), []))
        items_by_employee[e.id] = items
        all_checklist_ids.update(c.id for c in items)

    done_counts = defaultdict(int)
    for emp_id in TrainingProgress.objects.filter(
        employee_id__in=[e.id for e in employees],
        checklist_id__in=all_checklist_ids,
        status=TrainingProgress.Status.DONE,
    ).values_list('employee_id', flat=True):
        done_counts[emp_id] += 1

    result = {}
    for e in employees:
        total = len(items_by_employee[e.id])
        result[e.id] = round(done_counts[e.id] / total * 100) if total else 0
    return result


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


def batch_lms_marks(employees, threshold=None):
    """3 dau LMS/Danh gia (hoc/thi/ky nang) cho nhieu nhan su cung luc - tranh N+1 khi liet
    ke danh sach nhan su. Dung chung dieu kien voi lms_done/exam_pass."""
    from django.conf import settings

    from cls_sync.models import CourseResult, ExamResult

    threshold = settings.COMMISSION_EXAM_THRESHOLD if threshold is None else threshold
    employees = list(employees)
    employee_ids = [e.id for e in employees]

    course_done_ids = set(
        CourseResult.objects.filter(employee_id__in=employee_ids, status='Đạt')
        .values_list('employee_id', flat=True)
    )
    exam_pass_ids = set(
        ExamResult.objects.filter(employee_id__in=employee_ids, passed=True, score__gte=threshold)
        .values_list('employee_id', flat=True)
    )
    return {
        e.id: {
            'course': e.id in course_done_ids,
            'exam': e.id in exam_pass_ids,
            'skill': e.skill_result == 'Đạt',
        }
        for e in employees
    }


def latest_skill_eval_percent(employee):
    """% cua lan danh gia ky nang BQL (Skill_BQL) gan nhat da Hoan thanh."""
    from evaluation.models import Evaluation

    ev = (
        Evaluation.objects.filter(employee=employee, eval_type='Skill_BQL', status='done')
        .order_by('-completed_at')
        .first()
    )
    return float(ev.percent) if ev else None


# Cửa sổ thời gian AM/KCS được đánh giá random sau khi nhân sự hoàn thành đào tạo (phản hồi #7 mục 5).
RANDOM_EVAL_WINDOW_DAYS = 15


def training_completed_date(employee):
    """Ngày tiến độ đào tạo đạt 100% = completed_at muộn nhất trong các checklist đã Hoàn thành
    (chỉ khi đã đủ 100%). None nếu chưa đạt 100%."""
    if checklist_progress_percent(employee) < 100:
        return None
    from checklist.models import TrainingProgress

    items = matching_checklist_items(employee)
    last = (
        TrainingProgress.objects.filter(
            employee=employee, checklist_id__in=[c.id for c in items],
            status=TrainingProgress.Status.DONE, completed_at__isnull=False,
        )
        .order_by('-completed_at')
        .first()
    )
    return last.completed_at.date() if last else None


def random_eval_deadline(employee):
    """Hạn cuối AM/KCS được đánh giá random = ngày hoàn thành đào tạo + 15 ngày. None nếu chưa
    hoàn thành đào tạo (chưa tính hạn)."""
    done_date = training_completed_date(employee)
    return done_date + datetime.timedelta(days=RANDOM_EVAL_WINDOW_DAYS) if done_date else None


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

    # Cấp O (mục 7): PASS = LMS + thi + đào tạo tại điểm 100% + vận hành ca đạt (AM/KCS)
    # + tay nghề đạt (hội đồng) + phỏng vấn đạt (hội đồng).
    if is_bep_truong_pho or is_quan_ly_giam_sat:
        ok = (
            eligible and exam_pass(employee)
            and checklist_progress_percent(employee) >= 100
            and employee.shift_ops == 'Đạt'
            and employee.skill_result == 'Đạt'
            and employee.interview_result == 'Đạt'
        )
        return 'Pass thử việc' if ok else 'Tiếp tục thử việc'

    # Nhan vien thuong (cap S): PASS = LMS học xong ∧ đào tạo tại điểm 100% ∧ thi lý thuyết đạt
    # ∧ đánh giá thực hành đạt (phản hồi #7 mục 2). Bỏ công thức trung bình 0.4/0.6 của ĐỢT 2.
    if not eligible:
        return 'Tiếp tục thử việc'
    if checklist_progress_percent(employee) < 100:
        return 'Tiếp tục thử việc'
    if not exam_pass(employee):
        return 'Tiếp tục thử việc'
    skill_percent = float(employee.skill_score) * 100 if employee.skill_score is not None else 0
    if skill_percent < 85:  # đạt đánh giá thực hành ≥ 85% (khớp hệ cũ)
        return 'Tiếp tục thử việc'
    return 'Pass thử việc'


def recompute_final_result(employee):
    employee.final_result = compute_final_result(employee)
    employee.save(update_fields=['final_result'])
    return employee.final_result


def change_employee_status(employee, new_status):
    """Doi trang thai lam viec cua nhan su + tinh lai ket qua thu viec. Port
    EmployeeService.gs::changeStatus (khong co state-machine kiem tra chuyen trang thai,
    giong ban goc). M4.3: khi Nghi viec -> dong cac dot dang mo de khong treo bao cao."""
    employee.employee_status = new_status
    employee.save(update_fields=['employee_status'])
    if new_status == 'resigned':
        _close_open_enrollments_on_resign(employee)
    return recompute_final_result(employee)


def _close_open_enrollments_on_resign(employee):
    """Nhân sự nghỉ việc → đóng đợt thăng tiến (M1) và đợt đào tạo nguồn (M2) đang mở của họ
    (đưa về 'Không đạt'), để danh sách/báo cáo không còn coi là đang diễn ra."""
    from django.utils import timezone

    from .models import LevelUpEnrollment

    now = timezone.now()
    LevelUpEnrollment.objects.filter(
        employee=employee, status__in=['registered', 'training'],
    ).update(status='failed', completed_at=now)
    try:
        from sourcing.models import Enrollment as CohortEnrollment

        CohortEnrollment.objects.filter(
            employee=employee, status__in=['registered', 'studying'],
        ).update(status='failed', completed_at=now)
    except Exception:  # noqa: BLE001 - app sourcing có thể chưa migrate ở môi trường cũ
        pass


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
