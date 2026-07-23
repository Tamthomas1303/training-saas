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
    # Nạp sẵn các vị trí đã đạt hiện có (tránh N+1) — set (employee_id, target_position).
    existing = set(
        LevelUpEnrollment.objects.filter(tenant=tenant, status=LevelUpEnrollment.Status.COMPLETED)
        .values_list('employee_id', 'target_position')
    )
    to_create = []
    skipped = 0
    for r in rows:
        employee = emp_by_code.get((r.get('Employee_ID') or '').strip())
        if not employee:
            skipped += 1
            continue
        entry_key = normalize_key(checklist_position(employee.position))
        for col, pos in PASS_MAP.items():
            if not _checked(r.get(col)):
                continue
            if normalize_key(checklist_position(pos)) == entry_key:
                continue  # trùng vị trí vào làm — không tạo enrollment
            if (employee.id, pos) in existing:
                continue
            existing.add((employee.id, pos))
            to_create.append(LevelUpEnrollment(
                tenant=tenant, employee=employee, target_position=pos,
                status=LevelUpEnrollment.Status.COMPLETED,
            ))
    if to_create:
        LevelUpEnrollment.objects.bulk_create(to_create, batch_size=500)
    return {'created': len(to_create), 'skipped_no_employee': skipped}


# ---------- B2: lịch sử tham gia khóa BQL → Program/Cohort/Session/Attendance ----------
def sync_courses(tenant):
    rows = load_rows_smart(_url_for(tenant, 'courses')) if _url_for(tenant, 'courses') else []
    if not rows:
        return {'cohorts': 0, 'sessions': 0, 'attendances': 0, 'detail': 'Chưa cấu hình link Khóa học.'}
    from sourcing.models import Attendance, Cohort, CohortSession, Enrollment, Program

    emp_by_code = {e.code: e for e in Employee.objects.filter(tenant=tenant)}
    program, _ = Program.objects.get_or_create(
        tenant=tenant, name='Đào tạo Ban quản lý (lịch sử)',
        defaults={'audience': 'management', 'mode': 'offline',
                  'description': 'Nhập từ Raw_Data_Khoa_Hoc (Auto Syncing).'},
    )

    # Chỉ giữ dòng có nhân sự khớp.
    valid = []
    skipped = 0
    for r in rows:
        emp = emp_by_code.get((r.get('Employee_ID') or '').strip())
        if not emp:
            skipped += 1
            continue
        valid.append((r, emp))

    # 1) Cohort theo Cousera_Code (get_or_create — số ít, ≤ ~25).
    cohort_by_key = {}
    for r, _emp in valid:
        code = (r.get('Cousera_Code') or '').strip()
        name = (r.get('Cousera_Name') or '').strip()
        key = code or name
        if key and key not in cohort_by_key:
            cohort_by_key[key], _ = Cohort.objects.get_or_create(
                tenant=tenant, program=program, name=f'{code} — {name}'.strip(' —'),
                defaults={'status': 'closed'},
            )

    # 2) Session theo (cohort, Class_Code) (≤ ~110).
    session_by_key = {}
    for r, _emp in valid:
        key = (r.get('Cousera_Code') or '').strip() or (r.get('Cousera_Name') or '').strip()
        cohort = cohort_by_key.get(key)
        if not cohort:
            continue
        cls = (r.get('Class_Code') or '').strip() or (r.get('Cousera_Name') or '').strip()
        skey = (cohort.id, cls)
        if skey not in session_by_key:
            session_by_key[skey], _ = CohortSession.objects.get_or_create(
                tenant=tenant, cohort=cohort, title=cls,
                defaults={'date': _parse_date(r.get('Training_Date'))},
            )

    cohort_ids = [c.id for c in cohort_by_key.values()]
    session_ids = [s.id for s in session_by_key.values()]

    # 3) Enrollment (cohort, employee) — bulk.
    enr_id = {
        (e.cohort_id, e.employee_id): e.id
        for e in Enrollment.objects.filter(cohort_id__in=cohort_ids)
    }
    need_enr = set()
    for r, emp in valid:
        key = (r.get('Cousera_Code') or '').strip() or (r.get('Cousera_Name') or '').strip()
        cohort = cohort_by_key.get(key)
        if cohort and (cohort.id, emp.id) not in enr_id:
            need_enr.add((cohort.id, emp.id))
    new_enr = [
        Enrollment(tenant=tenant, cohort_id=cid, employee_id=eid, status='completed')
        for cid, eid in need_enr
    ]
    for e in Enrollment.objects.bulk_create(new_enr, batch_size=500):
        enr_id[(e.cohort_id, e.employee_id)] = e.id

    # 4) Attendance (session, enrollment) — bulk.
    existing_att = set(
        Attendance.objects.filter(session_id__in=session_ids).values_list('session_id', 'enrollment_id')
    )
    new_att = []
    for r, emp in valid:
        key = (r.get('Cousera_Code') or '').strip() or (r.get('Cousera_Name') or '').strip()
        cohort = cohort_by_key.get(key)
        if not cohort:
            continue
        cls = (r.get('Class_Code') or '').strip() or (r.get('Cousera_Name') or '').strip()
        sid = session_by_key[(cohort.id, cls)].id
        eid = enr_id.get((cohort.id, emp.id))
        if eid is None or (sid, eid) in existing_att:
            continue
        existing_att.add((sid, eid))
        new_att.append(Attendance(
            tenant=tenant, session_id=sid, enrollment_id=eid, present=True,
            method='manual', checked_in_at=None,
        ))
    Attendance.objects.bulk_create(new_att, batch_size=500)
    return {
        'cohorts': len(cohort_by_key), 'sessions': len(session_by_key),
        'enrollments': len(new_enr), 'attendances': len(new_att), 'skipped_no_employee': skipped,
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
