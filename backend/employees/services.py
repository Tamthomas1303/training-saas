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


def _o_position(position):
    """Vị trí thuộc cấp O (Ban quản lý)."""
    p = normalize_key(position)
    return any(k in p for k in ('quản lý', 'giám sát', 'bếp trưởng', 'bếp phó'))


def derive_level_group(position, job_level):
    """Suy nhóm level từ vị trí + Job_Level (#7). Vị trí cấp O → 'O'; còn lại theo chữ đầu
    Job_Level (S/O/P), mặc định 'S'."""
    if _o_position(position):
        return 'O'
    letter = (job_level or '').strip().upper()[:1]
    return letter if letter in ('S', 'O', 'P') else 'S'


def emp_type(employee):
    """Nhan cap (S/P/O) suy TRUC TIEP tu chu dau job_level - CHI dung de hien thi nhan (S)/(P)/(O)
    canh vi tri o danh sach nhan su, KHAC voi level_group (uu tien vi tri cap O, dung cho logic
    nghiep vu thang tien/Ban quan ly - xem derive_level_group). Tra ve '' neu job_level rong/
    khong xac dinh (khong mac dinh ve 'S' nhu level_group, vi day la nhan hien thi)."""
    letter = (employee.job_level or '').strip().upper()[:1]
    return letter if letter in ('S', 'O', 'P') else ''


def checklist_progress_percent(employee, position=None):
    """% tien do dao tao = so checklist da Hoan thanh / tong so checklist khop brand+position.
    position=None -> vi tri hien tai; truyen vi tri dich de tinh tien do vong thang tien (M1.4)."""
    # #4: nhân sự cũ (is_legacy) mặc định ĐÃ hoàn thành đào tạo vị trí vào làm (position=None).
    if position is None and getattr(employee, 'is_legacy', False):
        return 100
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


def checklist_progress_by_phase(employee, position=None):
    """Khung noi dung cap S - Buoc 2 (Prompt_KhungNoiDung_CapS_Buoc2.md muc 3) - tach 2 tien do
    theo Checklist.phase: 'core' (thu viec) va 'full' (toan bo, GIONG HET
    checklist_progress_percent hien co). Khong xoa/doi checklist_progress_percent - noi khac
    van goi ham do binh thuong; ham nay chi dung o noi CAN tach core/full (cong 1/cong 2).

    Tra ve {core_done, core_total, core_pct, full_done, full_total, full_pct}. `core_pct` = 100
    khi core_total=0 (vi tri khong co muc core nao - vd tat ca da phan loai completion, hoac
    chua co checklist gi) - "khong chan oan", coi nhu da dat dieu kien core (khong co gi de hoc)."""
    if position is None and getattr(employee, 'is_legacy', False):
        return {'core_done': 0, 'core_total': 0, 'core_pct': 100, 'full_done': 0, 'full_total': 0, 'full_pct': 100}

    from checklist.models import TrainingProgress

    items = matching_checklist_items(employee, position)
    full_total = len(items)
    if full_total == 0:
        return {'core_done': 0, 'core_total': 0, 'core_pct': 100, 'full_done': 0, 'full_total': 0, 'full_pct': 0}

    core_ids = {c.id for c in items if c.phase == 'core'}
    all_ids = [c.id for c in items]
    done_ids = set(
        TrainingProgress.objects.filter(
            employee=employee, checklist_id__in=all_ids, status=TrainingProgress.Status.DONE,
        ).values_list('checklist_id', flat=True)
    )
    core_total = len(core_ids)
    core_done = len(done_ids & core_ids)
    full_done = len(done_ids)

    return {
        'core_done': core_done, 'core_total': core_total,
        'core_pct': round(core_done / core_total * 100) if core_total else 100,
        'full_done': full_done, 'full_total': full_total,
        'full_pct': round(full_done / full_total * 100),
    }


def probation_checklist_ok(employee, position=None):
    """Khung noi dung cap S - Buoc 2 muc 4 - dieu kien CHECKLIST cua 'cong 1' (du dieu kien thi
    ket thuc thu viec / dat thu viec). GradingConfig.has_probation=True (mac dinh): can CORE
    100% - vi mac dinh MOI muc = core, dieu nay TUONG DUONG "100% toan bo" cu cho toi khi admin
    phan loai rieng (regression an toan). has_probation=False: BO dieu kien nay (luon coi la dat
    - "xac nhan tiep tuc theo quy che DN", cac dieu kien khac cua cong 1 - LMS/thi/ky nang -
    KHONG doi, van duoc kiem doc lap o noi goi ham nay)."""
    from accounts.services import get_grading_config

    if not get_grading_config(employee.tenant).has_probation:
        return True
    return checklist_progress_by_phase(employee, position)['core_pct'] >= 100


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
    """Port ProbationService.gs::_examPass (Config.examPass(), mac dinh doc tu GradingConfig -
    UI dot 3). Dung final_score (COALESCE score_adjusted, score) de diem phuc khao (neu co) uu
    tien hon diem CLS goc - khong con doi hoi passed=True cua CLS, vi phuc khao co the lat 1
    luot truot thanh dat."""
    from django.db.models.functions import Coalesce

    from accounts.services import get_grading_config
    from cls_sync.models import ExamResult

    threshold = get_grading_config(employee.tenant).exam_pass_percent if threshold is None else threshold
    return (
        ExamResult.objects.filter(employee=employee)
        .annotate(computed_score=Coalesce('score_adjusted', 'score'))
        .filter(computed_score__gte=threshold)
        .exists()
    )


def batch_lms_marks(employees, threshold=None):
    """3 dau LMS/Danh gia (hoc/thi/ky nang) cho nhieu nhan su cung luc - tranh N+1 khi liet
    ke danh sach nhan su. Dung chung dieu kien voi lms_done/exam_pass (final_score, xem do)."""
    employees = list(employees)
    if not employees:
        # UI Nhom 1 muc A: 1 trang co the loc list_tab ra 0 dong (vd tenant khong con ai dang
        # 'probation') - truoc day hau nhu khong xay ra nen chua lo, nhung KHONG duoc de threshold
        # roi thanh None (Django bao 'Cannot use None as a query value' o computed_score__gte).
        return {}

    from django.db.models.functions import Coalesce

    from accounts.services import get_grading_config
    from cls_sync.models import CourseResult, ExamResult

    if threshold is None:
        threshold = get_grading_config(employees[0].tenant).exam_pass_percent
    employee_ids = [e.id for e in employees]

    course_done_ids = set(
        CourseResult.objects.filter(employee_id__in=employee_ids, status='Đạt')
        .values_list('employee_id', flat=True)
    )
    exam_pass_ids = set(
        ExamResult.objects.filter(employee_id__in=employee_ids)
        .annotate(computed_score=Coalesce('score_adjusted', 'score'))
        .filter(computed_score__gte=threshold)
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


def batch_exam_score(employees):
    """Nhom 1 muc A - diem thi CAO NHAT (best_exam_score, xem ham do) cho nhieu nhan su cung
    luc, tranh N+1 o cot 'Ket qua thi' cua tab 'Dang lam viec'/'Ban quan ly' (danh sach nhan su).
    Tra ve {employee_id: diem hoac None neu chua thi lan nao}."""
    from django.db.models import Max
    from django.db.models.functions import Coalesce

    from cls_sync.models import ExamResult

    employee_ids = [e.id for e in employees]
    rows = (
        ExamResult.objects.filter(employee_id__in=employee_ids)
        .annotate(computed_score=Coalesce('score_adjusted', 'score'))
        .values('employee_id')
        .annotate(best=Max('computed_score'))
    )
    return {row['employee_id']: row['best'] for row in rows}


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
    """Diem thi dung cho muc 'Diem thi ly thuyet' trong phieu ket qua thu viec
    (build_probation_result_pdf) - lay DIEM CAO NHAT trong tat ca cac luot thi, dung
    final_score (COALESCE score_adjusted, score - xem ExamResult.final_score) nen diem phuc
    khao (Task 2, da co model that su - ExamResult.score_adjusted) tu dong duoc uu tien."""
    from django.db.models.functions import Coalesce

    from cls_sync.models import ExamResult

    best = (
        ExamResult.objects.filter(employee=employee)
        .annotate(computed_score=Coalesce('score_adjusted', 'score'))
        .filter(computed_score__isnull=False)
        .order_by('-computed_score')
        .first()
    )
    return float(best.computed_score) if best else 0


def compute_final_result(employee):
    """Ket qua thu viec (cot T). Port ProbationService.gs::computeFinalResult, phan theo
    Operation_Unit/Job_Position dung y ban goc. Don gian hoa 2 diem (theo quyet dinh khi lam
    ĐỢT 2 - "cong thuc thu viec"): 'eligible' (du DK thi) dung lms_done() thay vi diem khoa
    'Hoi nhap' rieng; 'theory' dung diem thi cao nhat cua NV (khong tach lan 1/lan 2-3)."""
    from .models import Employee

    if employee.employee_status == Employee.EmployeeStatus.RESIGNED:
        return 'Đã nghỉ việc'

    # #4: nhân sự cũ (vào trước 1/7) mặc định đã hoàn thành thử việc vị trí vào làm.
    if getattr(employee, 'is_legacy', False):
        return 'Pass thử việc'

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
    # Khung noi dung cap S - Buoc 2 muc 4: "dao tao tai diem 100%" nay dung probation_checklist_ok
    # (core 100% khi has_probation=True - mac dinh MOI muc = core nen TUONG DUONG "100% toan bo"
    # cu cho toi khi admin phan loai; bo qua hoan toan khi has_probation=False).
    if is_bep_truong_pho or is_quan_ly_giam_sat:
        ok = (
            eligible and exam_pass(employee)
            and probation_checklist_ok(employee)
            and employee.shift_ops == 'Đạt'
            and employee.skill_result == 'Đạt'
            and employee.interview_result == 'Đạt'
        )
        return 'Pass thử việc' if ok else 'Tiếp tục thử việc'

    # Nhan vien thuong (cap S): PASS = LMS học xong ∧ đào tạo tại điểm 100% ∧ thi lý thuyết đạt
    # ∧ đánh giá thực hành đạt (phản hồi #7 mục 2). Bỏ công thức trung bình 0.4/0.6 của ĐỢT 2.
    if not eligible:
        return 'Tiếp tục thử việc'
    if not probation_checklist_ok(employee):
        return 'Tiếp tục thử việc'
    if not exam_pass(employee):
        return 'Tiếp tục thử việc'
    from accounts.services import get_grading_config

    skill_percent = float(employee.skill_score) * 100 if employee.skill_score is not None else 0
    if skill_percent < get_grading_config(employee.tenant).skill_pass_percent:  # UI dot 3
        return 'Tiếp tục thử việc'
    return 'Pass thử việc'


def recompute_final_result(employee):
    """Tinh lai final_result; dong bo pass_date (ngay dung de tinh luong) theo do: CHI set
    pass_date = hom nay khi final_result THAT SU CHUYEN sang 'Pass thu viec' (final_result CU
    khac 'Pass thu viec', xem truoc khi ghi de) - KHONG backfill hom nay cho nguoi da Pass tu
    truoc (vd goi lai recompute nhieu lan sau khi da Pass khong duoc doi pass_date). Khi roi
    khoi 'Pass thu viec' thi xoa pass_date.

    Luu y: ham nay duoc goi rat nhieu noi (checklist/evaluation hoan thanh, sync_cls, API
    recompute-final...) - neu chi kiem tra "pass_date dang trong" nhu truoc day se backfill
    SAI ngay Pass moi lan goi cho nguoi da Pass tu lau nhung pass_date bi trong (vd du lieu cu
    truoc khi co truong nay). Xem management command clear_backfilled_pass_date de don du
    lieu da bi ghi sai boi loi cu."""
    previous_result = employee.final_result
    employee.final_result = compute_final_result(employee)
    update_fields = ['final_result']
    became_pass = employee.final_result == 'Pass thử việc' and previous_result != 'Pass thử việc'
    left_pass = employee.final_result != 'Pass thử việc' and employee.pass_date
    if became_pass:
        employee.pass_date = datetime.date.today()
        update_fields.append('pass_date')
    elif left_pass:
        employee.pass_date = None
        update_fields.append('pass_date')
    employee.save(update_fields=update_fields)
    if became_pass:
        # Nhom 3B luong 5 (Prompt_Nhom3B_ThiThuViec_TuDong.md muc 4): vua CHUYEN sang Pass thu
        # viec -> gui email ket qua toi QLNH nha hang (neu bat cong tac), idempotent theo
        # pass_date (xem employees.automation.notify_probation_result_if_needed).
        _notify_probation_result_safe(employee, 'pass', employee.pass_date)
    return employee.final_result


def _notify_probation_result_safe(employee, result, decision_date):
    """Wrapper an toan (cung mau voi _on_course_completed_safe/_log_xapi_safe cua cac app khac) -
    loi gui email ket qua thu viec KHONG duoc phep chan luong tinh ket qua thu viec (co the goi
    tu rat nhieu noi: checklist/evaluation hoan thanh, sync_cls, API...)."""
    try:
        from .automation import notify_probation_result_if_needed

        notify_probation_result_if_needed(employee, result, decision_date)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            'Gui email ket qua thu viec that bai cho nhan su %s - da bo qua.', employee.id,
        )


def change_employee_status(employee, new_status):
    """Doi trang thai lam viec cua nhan su + tinh lai ket qua thu viec. Port
    EmployeeService.gs::changeStatus (khong co state-machine kiem tra chuyen trang thai,
    giong ban goc). M4.3: khi Nghi viec -> dong cac dot dang mo de khong treo bao cao.

    resigned_at ghi ngay chuyen sang 'resigned' (CHI khi employee_status CU khac 'resigned' -
    khong backfill neu goi lai cho nguoi da 'resigned' tu truoc ma resigned_at dang trong),
    xoa neu roi khoi 'resigned' - dung de bao cao dao tao tuan/thang dem dung so nghi viec
    TRONG KY (Employee khong co lich su trang thai, day la moc thoi gian duy nhat)."""
    from .models import Employee

    previous_status = employee.employee_status
    employee.employee_status = new_status
    update_fields = ['employee_status']
    became_resigned = (
        new_status == Employee.EmployeeStatus.RESIGNED
        and previous_status != Employee.EmployeeStatus.RESIGNED
    )
    left_resigned = new_status != Employee.EmployeeStatus.RESIGNED and employee.resigned_at
    if became_resigned:
        employee.resigned_at = datetime.date.today()
        update_fields.append('resigned_at')
    elif left_resigned:
        employee.resigned_at = None
        update_fields.append('resigned_at')
    employee.save(update_fields=update_fields)
    if new_status == 'resigned':
        _close_open_enrollments_on_resign(employee)
    result = recompute_final_result(employee)
    # Nhom 3B luong 5: nghi viec NGAY TU LUC dang thu viec = tien de gan nhat co that trong he
    # thong hien tai cho "chot Khong dat" (Employee chua co trang thai rieng cho truong hop nay -
    # xem ProbationResultNotification docstring). Nghi viec sau khi DA Pass (probation xong tu
    # truoc) KHONG tinh la ket qua thu viec - khong gui o day.
    if became_resigned and previous_status == Employee.EmployeeStatus.PROBATION:
        _notify_probation_result_safe(employee, 'failed', employee.resigned_at)
    return result


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
    lien quan hoa hong: khong tinh final_result/computeFinalResult - thuoc sprint khac).
    UI dot 3: nguong thi/ky nang dung rieng allowance_exam_min/allowance_skill_min cua
    GradingConfig (nhom "Phu cap"), doc lap voi exam_pass_percent/skill_pass_percent (nhom
    "Thi"/"Ky nang" dung cho cac noi goi exam_pass() khac khong truyen threshold) - dong y
    ban gia tri mac dinh giong nhau (deu seed tu COMMISSION_EXAM/SKILL_THRESHOLD) nen KHONG
    doi ket qua hien tai."""
    from django.conf import settings

    from accounts.services import get_grading_config

    config = get_grading_config(employee.tenant)
    lms = lms_done(employee)
    exam = exam_pass(employee, threshold=config.allowance_exam_min)
    training = checklist_progress_percent(employee) >= 100
    skill_percent = latest_skill_eval_percent(employee)
    skill_pass = skill_percent is not None and skill_percent >= config.allowance_skill_min
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
