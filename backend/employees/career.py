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
    from evaluation.services import levelup_skill_evaluation
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
    }


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
