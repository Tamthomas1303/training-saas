"""
career.py — logic đào tạo theo lộ trình thăng tiến (v2.1 / M1).

Quy tắc đã chốt:
  - Level chỉ tính "major" S1 → S2 → S3 (bỏ qua bậc nhỏ S1.1…).
  - BQL tự chọn vị trí mới (cùng khối, chưa đạt) → hoàn thành 1 vị trí = lên 1 major level.
  - Đủ 3 vị trí (gồm vị trí vào làm) = S3 → vào nhân sự nguồn.
  - Chặn mốc 3 tháng ở vị trí hiện tại mới cho đăng ký vị trí tiếp.
"""
import re
import unicodedata
from datetime import date

from django.utils import timezone

from .models import LevelUpEnrollment

MAX_MAJOR = 3
MIN_MONTHS_BETWEEN = 3
POSITIONS_FOR_TALENT_POOL = 3

# 3 đợt thi/năm: tháng 4 / 8 / 12. Đăng ký trước tối thiểu 1 tháng.
EXAM_MONTHS = (4, 8, 12)
EXAM_REGISTER_LEAD_MONTHS = 1

# M1.5 — lên level: điểm tổng = 40% thi lý thuyết + 60% đánh giá thực hành, phải ≥ 85%.
LEVELUP_PASS_THRESHOLD = 85
LEVELUP_EXAM_WEIGHT = 0.4
LEVELUP_SKILL_WEIGHT = 0.6


def _no_accent(text):
    s = unicodedata.normalize('NFD', (text or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower().replace('đ', 'd')


def zone_of_position(position):
    """FOH (Phục vụ/Runner/Pha chế/Thu ngân) hay BOH (Bếp thớt/salad/chảo/cơm gà)."""
    return 'BOH' if 'bep' in _no_accent(position) else 'FOH'


def major_level(job_level):
    """'S1.1' -> 'S1', 'P2.1' -> 'P2'. Trả '' nếu không đọc được."""
    m = re.match(r'\s*([A-Za-z]*\d+)', str(job_level or ''))
    return m.group(1).upper() if m else ''


def _split_major(major):
    m = re.match(r'([A-Za-z]*)(\d+)', major or '')
    return (m.group(1), int(m.group(2))) if m else ('', 0)


def next_major_level(major):
    """Major kế tiếp (S1->S2); '' nếu đã tối đa (>=3)."""
    letter, num = _split_major(major)
    if not num or num >= MAX_MAJOR:
        return ''
    return f'{letter}{num + 1}'


def last_position_date(employee):
    """Ngày đạt vị trí gần nhất = completed_at muộn nhất của enrollment đã hoàn thành; nếu chưa có
    (còn ở vị trí vào làm) thì lấy ngày vào làm."""
    last = (
        LevelUpEnrollment.objects.filter(employee=employee, status='completed', completed_at__isnull=False)
        .order_by('-completed_at')
        .first()
    )
    return last.completed_at.date() if last else employee.start_date


def months_worked_at_current(employee):
    d = last_position_date(employee)
    if not d:
        return None
    return (timezone.now().date() - d).days / 30.0


def positions_achieved_count(employee):
    """Số vị trí đã đạt = 1 (vị trí vào làm) + số đợt thăng tiến đã hoàn thành."""
    return 1 + LevelUpEnrollment.objects.filter(employee=employee, status='completed').count()


def eligible_for_talent_pool(employee):
    return positions_achieved_count(employee) >= POSITIONS_FOR_TALENT_POOL


def achieved_positions(employee):
    """Danh sách vị trí đã đạt: vị trí vào làm + các vị trí đã hoàn thành thăng tiến."""
    positions = [employee.position] if employee.position else []
    positions += list(
        LevelUpEnrollment.objects.filter(employee=employee, status='completed')
        .values_list('target_position', flat=True)
    )
    return positions


def registration_status(employee):
    """Trạng thái cho việc đăng ký vị trí tiếp: can(bool) + reason + level hiện tại/đích."""
    current = major_level(employee.job_level)
    nxt = next_major_level(current)
    open_enr = LevelUpEnrollment.objects.filter(
        employee=employee, status__in=['registered', 'training']
    ).exists()
    months = months_worked_at_current(employee)

    if not nxt:
        return {'can': False, 'reason': f'Đã đạt major level tối đa ({current or "?"}).',
                'current_level': current, 'next_level': ''}
    if open_enr:
        return {'can': False, 'reason': 'Đang có một đợt thăng tiến chưa hoàn thành.',
                'current_level': current, 'next_level': nxt}
    if months is not None and months < MIN_MONTHS_BETWEEN:
        return {'can': False, 'reason': f'Chưa đủ 3 tháng ở vị trí hiện tại (mới ~{months:.1f} tháng).',
                'current_level': current, 'next_level': nxt}
    return {'can': True, 'reason': '', 'current_level': current, 'next_level': nxt}


def eligible_target_positions(employee):
    """Vị trí đích BQL được chọn: lấy từ checklist của tenant, CÙNG KHỐI (FOH/BOH) với vị trí
    hiện tại, LOẠI các vị trí nhân sự đã đạt. Không có thứ tự — BQL tự chọn."""
    from checklist.models import Checklist

    zone = zone_of_position(employee.position)
    achieved = {_no_accent(p) for p in achieved_positions(employee)}
    positions = set(
        Checklist.objects.filter(tenant=employee.tenant)
        .exclude(position='')
        .values_list('position', flat=True)
    )
    out = []
    for p in sorted(positions):
        if zone_of_position(p) != zone:
            continue
        if _no_accent(p) in achieved:
            continue
        out.append(p)
    return out


def _minus_months(d, months):
    m = d.month - months
    y = d.year
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def upcoming_exam_batches(today=None, horizon_months=14):
    """3 đợt thi/năm (T4/T8/T12). Trả các đợt còn MỞ đăng ký: hôm nay phải trước ngày đầu đợt
    ít nhất 1 tháng. Mỗi đợt: code '2026-T4', label, ngày thi (đầu tháng), hạn đăng ký."""
    today = today or timezone.now().date()
    out = []
    year = today.year
    for y in (year, year + 1):
        for m in EXAM_MONTHS:
            exam_date = date(y, m, 1)
            deadline = _minus_months(exam_date, EXAM_REGISTER_LEAD_MONTHS)
            if today >= deadline:
                continue  # đã quá hạn đăng ký (trong vòng 1 tháng trước đợt) hoặc đã qua
            if (exam_date.year - today.year) * 12 + (exam_date.month - today.month) > horizon_months:
                continue
            out.append({
                'code': f'{y}-T{m}',
                'label': f'Đợt T{m}/{y}',
                'exam_date': exam_date.isoformat(),
                'register_deadline': deadline.isoformat(),
            })
    return out


def _valid_batch_codes(today=None):
    return {b['code'] for b in upcoming_exam_batches(today)}


def register_levelup(employee, target_position, exam_batch, user):
    """BQL đăng ký nhân sự cho MỘT vị trí đích + đợt thi. Trả (enrollment, None) nếu thành công,
    hoặc (None, 'lý do') nếu bị chặn. Chốt lại toàn bộ điều kiện ở server."""
    status = registration_status(employee)
    if not status['can']:
        return None, status['reason']

    target_position = (target_position or '').strip()
    if not target_position:
        return None, 'Chưa chọn vị trí đích.'
    if target_position not in eligible_target_positions(employee):
        return None, 'Vị trí đích không hợp lệ (phải cùng khối và chưa đạt).'

    exam_batch = (exam_batch or '').strip()
    if exam_batch not in _valid_batch_codes():
        return None, 'Đợt thi không hợp lệ hoặc đã quá hạn đăng ký (đăng ký trước 1 tháng).'

    enrollment = LevelUpEnrollment.objects.create(
        tenant=employee.tenant,
        employee=employee,
        target_position=target_position,
        zone=zone_of_position(target_position),
        from_level=status['current_level'],
        target_level=status['next_level'],
        exam_batch=exam_batch,
        status=LevelUpEnrollment.Status.REGISTERED,
        registered_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    return enrollment, None


def open_training(enrollment):
    """Phòng Đào tạo ghép khoá CLS xong → mở vòng đào tạo (registered → training)."""
    if enrollment.status != LevelUpEnrollment.Status.REGISTERED:
        return False, 'Chỉ mở đào tạo cho đợt đang ở trạng thái "Đăng ký".'
    enrollment.status = LevelUpEnrollment.Status.TRAINING
    enrollment.save(update_fields=['status'])
    return True, None


def levelup_progress_percent(enrollment):
    """% tiến độ đào tạo của vòng = checklist VỊ TRÍ ĐÍCH đã Hoàn thành / tổng."""
    from .services import checklist_progress_percent

    return checklist_progress_percent(enrollment.employee, enrollment.target_position)


def levelup_round_detail(enrollment):
    """Dữ liệu 1 vòng thăng tiến để đào tạo + đánh giá (M1.4): checklist vị trí đích + trạng thái
    từng mục, % tiến độ, LMS/thi (theo dõi CLS), và kết quả đánh giá kỹ năng của vòng."""
    from checklist.models import TrainingProgress
    from evaluation.services import levelup_skill_evaluation, resolve_criteria
    from .services import exam_pass, lms_done, matching_checklist_items

    employee = enrollment.employee
    items = matching_checklist_items(employee, enrollment.target_position)
    status_by_checklist = dict(
        TrainingProgress.objects.filter(
            employee=employee, checklist_id__in=[c.id for c in items]
        ).values_list('checklist_id', 'status')
    )
    checklist = [
        {
            'id': c.id,
            'day': c.day,
            'category': c.category,
            'task_name': c.task_name,
            'doc_url': c.doc_url,
            'status': status_by_checklist.get(c.id, TrainingProgress.Status.PENDING),
        }
        for c in items
    ]
    done = sum(1 for c in checklist if c['status'] == TrainingProgress.Status.DONE)
    percent = round(done / len(checklist) * 100) if checklist else 0

    skill_eval = levelup_skill_evaluation(enrollment)
    _, criteria = resolve_criteria(employee, 'Skill_BQL', enrollment.target_position)
    return {
        'enrollment_id': enrollment.id,
        'employee_id': employee.id,
        'employee_name': employee.name,
        'target_position': enrollment.target_position,
        'zone': enrollment.zone,
        'from_level': enrollment.from_level,
        'target_level': enrollment.target_level,
        'exam_batch': enrollment.exam_batch,
        'status': enrollment.status,
        'checklist': checklist,
        'progress_percent': percent,
        'lms_done': lms_done(employee),
        'exam_pass': exam_pass(employee),
        'skill_percent': float(skill_eval.percent) if skill_eval else None,
        'skill_result': (skill_eval.result if skill_eval else ''),
        'criteria': criteria,
        'completion': levelup_completion_status(enrollment),
    }


def levelup_completion_status(enrollment):
    """M1.5 — kiểm 4 điều kiện lên level cho 1 vòng:
      1) LMS học xong  2) checklist vị trí đích 100%  3) thi đạt (CLS)
      4) điểm tổng 40% thi + 60% thực hành ≥ 85%.
    Trả dict chi tiết + can_complete + reason."""
    from evaluation.services import levelup_skill_evaluation
    from .services import best_exam_score, exam_pass, lms_done

    employee = enrollment.employee
    lms = lms_done(employee)
    checklist_pct = levelup_progress_percent(enrollment)
    checklist_ok = checklist_pct >= 100
    exam_ok = exam_pass(employee)
    exam_score = best_exam_score(employee)

    skill_eval = levelup_skill_evaluation(enrollment)
    skill_percent = float(skill_eval.percent) if skill_eval else None

    combined = None
    combined_ok = False
    if skill_percent is not None:
        combined = round(LEVELUP_EXAM_WEIGHT * exam_score + LEVELUP_SKILL_WEIGHT * skill_percent, 1)
        combined_ok = combined >= LEVELUP_PASS_THRESHOLD

    reasons = []
    if not lms:
        reasons.append('chưa hoàn thành LMS')
    if not checklist_ok:
        reasons.append(f'đào tạo vị trí đích mới {checklist_pct}%')
    if not exam_ok:
        reasons.append('chưa đạt thi lý thuyết')
    if skill_percent is None:
        reasons.append('chưa có đánh giá kỹ năng (Skill_BQL)')
    elif not combined_ok:
        reasons.append(f'điểm tổng {combined}% < 85%')

    already_open = enrollment.status == LevelUpEnrollment.Status.TRAINING
    can_complete = bool(lms and checklist_ok and exam_ok and combined_ok and already_open)
    return {
        'lms': lms,
        'checklist_percent': checklist_pct,
        'checklist_ok': checklist_ok,
        'exam_pass': exam_ok,
        'exam_score': exam_score,
        'skill_percent': skill_percent,
        'combined_score': combined,
        'combined_ok': combined_ok,
        'threshold': LEVELUP_PASS_THRESHOLD,
        'weights': {'exam': LEVELUP_EXAM_WEIGHT, 'skill': LEVELUP_SKILL_WEIGHT},
        'can_complete': can_complete,
        'reason': '' if can_complete else ('; '.join(reasons) or 'Vòng không ở trạng thái đang đào tạo.'),
    }


def complete_levelup(enrollment, user=None):
    """Chốt lên level nếu đủ điều kiện (M1.5): đánh dấu vòng hoàn thành + nâng major level +
    ghi vị trí đã đạt. Nếu đủ 3 vị trí (gồm vị trí vào làm) → S3 → thuộc diện nhân sự nguồn.
    Trả (result_dict, None) hoặc (None, 'lý do')."""
    status = levelup_completion_status(enrollment)
    if not status['can_complete']:
        return None, status['reason']

    employee = enrollment.employee
    enrollment.status = LevelUpEnrollment.Status.COMPLETED
    enrollment.completed_at = timezone.now()
    enrollment.save(update_fields=['status', 'completed_at'])

    # Nâng major level: giữ định dạng [chữ][major].[bậc nhỏ] → đặt về '.1' của major đích.
    target_major = enrollment.target_level or next_major_level(major_level(employee.job_level))
    if target_major:
        employee.job_level = f'{target_major}.1'
        employee.save(update_fields=['job_level'])

    count = positions_achieved_count(employee)
    is_talent_pool = eligible_for_talent_pool(employee)
    if is_talent_pool:
        note = (f'{employee.name} đã đạt vị trí "{enrollment.target_position}", lên {target_major} '
                f'và hoàn thành đủ {count} vị trí → vào danh sách NHÂN SỰ NGUỒN.')
    else:
        note = (f'{employee.name} đã đạt vị trí "{enrollment.target_position}", lên {target_major} '
                f'({count}/{POSITIONS_FOR_TALENT_POOL} vị trí).')

    return {
        'enrollment_id': enrollment.id,
        'employee_id': employee.id,
        'new_level': target_major,
        'job_level': employee.job_level,
        'target_position': enrollment.target_position,
        'positions_achieved_count': count,
        'achieved_positions': achieved_positions(employee),
        'is_talent_pool': is_talent_pool,
        'message': note,
    }, None


def fail_levelup(enrollment, user=None):
    """Đánh dấu vòng KHÔNG ĐẠT (đóng vòng, không lên level). Cho phép đăng ký lại đợt sau."""
    if enrollment.status not in (
        LevelUpEnrollment.Status.REGISTERED, LevelUpEnrollment.Status.TRAINING,
    ):
        return False, 'Vòng đã kết thúc, không thể đánh dấu không đạt.'
    enrollment.status = LevelUpEnrollment.Status.FAILED
    enrollment.completed_at = timezone.now()
    enrollment.save(update_fields=['status', 'completed_at'])
    return True, None


def talent_pool_employees(tenant):
    """Danh sách nhân sự nguồn (đủ 3 vị trí / major S3). Dẫn xuất — chưa cần field riêng (M2)."""
    from .models import Employee

    out = []
    for e in Employee.objects.filter(tenant=tenant).exclude(
        employee_status=Employee.EmployeeStatus.RESIGNED
    ):
        if eligible_for_talent_pool(e):
            out.append(e)
    return out


def levelup_eligible_list(employees):
    """G2 — danh sách theo dõi lộ trình: nhân sự cấp S còn dưới S3, kèm trạng thái đủ/chưa đủ
    điều kiện đăng ký thăng tiến (chặn 3 tháng + đợt đang mở). Tính theo lô, tránh N+1."""
    from collections import defaultdict

    from .models import LevelUpEnrollment

    cands = [e for e in employees if next_major_level(major_level(e.job_level))]
    ids = [e.id for e in cands]
    open_set = set(
        LevelUpEnrollment.objects.filter(employee_id__in=ids, status__in=['registered', 'training'])
        .values_list('employee_id', flat=True)
    )
    comp_count = defaultdict(int)
    comp_latest = {}
    for eid, cat in (
        LevelUpEnrollment.objects.filter(employee_id__in=ids, status='completed')
        .values_list('employee_id', 'completed_at')
    ):
        comp_count[eid] += 1
        if cat and (eid not in comp_latest or cat > comp_latest[eid]):
            comp_latest[eid] = cat

    today = timezone.now().date()
    rows = []
    for e in cands:
        current = major_level(e.job_level)
        nxt = next_major_level(current)
        last = comp_latest.get(e.id)
        last_date = last.date() if last else e.start_date
        months = round((today - last_date).days / 30.0, 1) if last_date else None
        has_open = e.id in open_set
        count = 1 + comp_count.get(e.id, 0)
        if has_open:
            can, reason = False, 'Đang có đợt thăng tiến chưa hoàn thành'
        elif months is not None and months < MIN_MONTHS_BETWEEN:
            can, reason = False, f'Chưa đủ 3 tháng ở vị trí hiện tại (~{months} tháng)'
        else:
            can, reason = True, ''
        rows.append({
            'employee_id': e.id, 'code': e.code, 'name': e.name,
            'restaurant_name': e.restaurant.name if e.restaurant else '',
            'position': e.position, 'current_level': current, 'next_level': nxt,
            'months_at_current': months, 'positions_achieved_count': count,
            'has_open': has_open, 'can': can, 'reason': reason,
        })
    rows.sort(key=lambda r: (not r['can'], r['name']))
    return rows


def levelup_options(employee):
    """Gói dữ liệu cho màn BQL đăng ký thăng tiến: level hiện tại/đích, khối, vị trí đã đạt,
    cổng đăng ký (can/reason), danh sách vị trí đích hợp lệ và các đợt thi còn mở."""
    status = registration_status(employee)
    return {
        **status,
        'zone': zone_of_position(employee.position),
        'current_position': employee.position,
        'achieved_positions': achieved_positions(employee),
        'positions_achieved_count': positions_achieved_count(employee),
        'eligible_for_talent_pool': eligible_for_talent_pool(employee),
        'options': eligible_target_positions(employee),
        'exam_batches': upcoming_exam_batches(),
    }
