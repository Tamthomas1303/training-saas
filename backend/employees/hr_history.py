"""
hr_history.py — Nhóm B: nạp LỊCH SỬ học/đánh giá từ các tab Auto Syncing.

  B1) Quanly_Lotrinh: cột Pass_* → vị trí đã đạt (cấp S) = LevelUpEnrollment completed.
  B2) Raw_Data_Khoa_Hoc: dựng đầy đủ Program/Cohort/Session/Attendance lịch sử (đào tạo BQL).
  B3) Input_DanhGia_BQL: kết quả cấp O → skill_result/shift_ops/interview_result.

Idempotent: chạy lại không nhân bản (khớp theo khóa tự nhiên).
"""
from datetime import datetime

from django.db import transaction

from .hr_import import _url_for, load_rows_smart
from .models import Employee, LevelUpEnrollment
from .services import checklist_position, normalize_key

# Cột Pass_* (Quanly_Lotrinh) → tên vị trí chuẩn.
PASS_MAP = {
    'Pass_PV': 'Phục vụ', 'Pass_PC': 'Pha chế', 'Pass_TN': 'Thu ngân',
    'Pass_BT': 'Bếp thớt', 'Pass_BS': 'Bếp salad', 'Pass_CG': 'Bếp cơm gà',
    'Pass_BC': 'Bếp chảo', 'Pass_HS': 'Chăm sóc bể hải sản',
}
DATE_FORMATS = ('%d/%m/%Y', '%Y/%m/%d', '%Y-%m-%d')


def _parse_date(value):
    value = (value or '').strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _checked(value):
    return bool((value or '').strip())


# ---------- B1: vị trí đã đạt (cấp S) ----------
def sync_pass_positions(tenant):
    rows = load_rows_smart(_url_for(tenant, 'lotrinh')) if _url_for(tenant, 'lotrinh') else []
    if not rows:
        return {'created': 0, 'skipped_no_employee': 0, 'detail': 'Chưa cấu hình link Lộ trình.'}
    emp_by_code = {e.code: e for e in Employee.objects.filter(tenant=tenant)}
    created = skipped = 0
    for r in rows:
        code = (r.get('Employee_ID') or '').strip()
        employee = emp_by_code.get(code)
        if not employee:
            skipped += 1
            continue
        entry_key = normalize_key(checklist_position(employee.position))
        for col, pos in PASS_MAP.items():
            if not _checked(r.get(col)):
                continue
            if normalize_key(checklist_position(pos)) == entry_key:
                continue  # trùng vị trí vào làm — không tạo enrollment
            exists = LevelUpEnrollment.objects.filter(
                employee=employee, target_position=pos, status=LevelUpEnrollment.Status.COMPLETED,
            ).exists()
            if exists:
                continue
            LevelUpEnrollment.objects.create(
                tenant=tenant, employee=employee, target_position=pos,
                status=LevelUpEnrollment.Status.COMPLETED,
            )
            created += 1
    return {'created': created, 'skipped_no_employee': skipped}


# ---------- B2: lịch sử tham gia khóa BQL → Program/Cohort/Session/Attendance ----------
def sync_courses(tenant):
    rows = load_rows_smart(_url_for(tenant, 'courses')) if _url_for(tenant, 'courses') else []
    if not rows:
        return {'sessions': 0, 'attendances': 0, 'detail': 'Chưa cấu hình link Khóa học.'}
    from sourcing.models import Attendance, Cohort, CohortSession, Enrollment, Program

    emp_by_code = {e.code: e for e in Employee.objects.filter(tenant=tenant)}

    program, _ = Program.objects.get_or_create(
        tenant=tenant, name='Đào tạo Ban quản lý (lịch sử)',
        defaults={'audience': 'management', 'mode': 'offline',
                  'description': 'Nhập từ Raw_Data_Khoa_Hoc (Auto Syncing).'},
    )

    cohort_cache, session_cache = {}, {}
    skipped = attendances = 0

    def get_cohort(cousera_code, cousera_name):
        key = cousera_code or cousera_name
        if key not in cohort_cache:
            cohort_cache[key], _ = Cohort.objects.get_or_create(
                tenant=tenant, program=program, name=f'{cousera_code} — {cousera_name}'.strip(' —'),
                defaults={'status': 'closed'},
            )
        return cohort_cache[key]

    def get_session(cohort, class_code, cousera_name, date):
        key = (cohort.id, class_code)
        if key not in session_cache:
            session_cache[key], _ = CohortSession.objects.get_or_create(
                tenant=tenant, cohort=cohort, title=class_code or cousera_name,
                defaults={'date': date},
            )
        return session_cache[key]

    for r in rows:
        code = (r.get('Employee_ID') or '').strip()
        employee = emp_by_code.get(code)
        if not employee:
            skipped += 1
            continue
        cohort = get_cohort((r.get('Cousera_Code') or '').strip(), (r.get('Cousera_Name') or '').strip())
        session = get_session(
            cohort, (r.get('Class_Code') or '').strip(), (r.get('Cousera_Name') or '').strip(),
            _parse_date(r.get('Training_Date')),
        )
        enrollment, _ = Enrollment.objects.get_or_create(
            tenant=tenant, cohort=cohort, employee=employee, defaults={'status': 'completed'},
        )
        _, created = Attendance.objects.get_or_create(
            tenant=tenant, session=session, enrollment=enrollment,
            defaults={'present': True, 'method': 'manual', 'checked_in_at': None},
        )
        attendances += int(created)
    return {
        'cohorts': len(cohort_cache), 'sessions': len(session_cache),
        'attendances': attendances, 'skipped_no_employee': skipped,
    }


# ---------- B3: kết quả cấp O ----------
def sync_bql_results(tenant):
    rows = load_rows_smart(_url_for(tenant, 'danhgia')) if _url_for(tenant, 'danhgia') else []
    if not rows:
        return {'updated': 0, 'detail': 'Chưa cấu hình link Input_DanhGia_BQL.'}
    emp_by_code = {e.code: e for e in Employee.objects.filter(tenant=tenant)}
    updated = skipped = 0
    to_update = []
    for r in rows:
        employee = emp_by_code.get((r.get('Employee_ID') or '').strip())
        if not employee:
            skipped += 1
            continue
        shift = (r.get('Assess_ShiftOps') or '').strip()
        interview = (r.get('Assess_Interview') or '').strip()
        voc = (r.get('Assess_Vocational') or '').strip()
        train = (r.get('Assess_TrainingSkill') or '').strip()
        skill = voc or train
        if shift:
            employee.shift_ops = shift
        if interview:
            employee.interview_result = interview
        if skill:
            employee.skill_result = skill
        to_update.append(employee)
        updated += 1
    if to_update:
        with transaction.atomic():
            Employee.objects.bulk_update(
                to_update, ['shift_ops', 'interview_result', 'skill_result'], batch_size=200,
            )
    return {'updated': updated, 'skipped_no_employee': skipped}


def sync_history(tenant):
    """Chạy cả 3 bước lịch sử (roster phải đồng bộ trước)."""
    return {
        'pass_positions': sync_pass_positions(tenant),
        'courses': sync_courses(tenant),
        'bql_results': sync_bql_results(tenant),
    }
