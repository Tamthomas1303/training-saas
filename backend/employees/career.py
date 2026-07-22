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

from django.utils import timezone

from .models import LevelUpEnrollment

MAX_MAJOR = 3
MIN_MONTHS_BETWEEN = 3
POSITIONS_FOR_TALENT_POOL = 3


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
