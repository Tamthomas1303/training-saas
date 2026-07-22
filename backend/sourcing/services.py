from django.utils import timezone

from .models import Attendance, Enrollment


def session_roster(session):
    """Danh sách học viên của đợt kèm trạng thái điểm danh cho MỘT buổi."""
    enrollments = (
        Enrollment.objects.filter(cohort=session.cohort)
        .select_related('employee', 'employee__restaurant')
        .order_by('employee__name')
    )
    att_by_enrollment = {a.enrollment_id: a for a in Attendance.objects.filter(session=session)}
    rows = []
    for e in enrollments:
        a = att_by_enrollment.get(e.id)
        rows.append({
            'enrollment_id': e.id,
            'employee_code': e.employee.code,
            'employee_name': e.employee.name,
            'restaurant_name': e.employee.restaurant.name if e.employee.restaurant else '',
            'present': bool(a and a.present),
            'method': a.method if a else '',
            'checked_in_at': a.checked_in_at.isoformat() if (a and a.checked_in_at) else None,
        })
    return rows


def mark_attendance(session, enrollment, present=True, method='self', user=None):
    """Ghi/điều chỉnh điểm danh 1 học viên cho 1 buổi. Trả (attendance, None) hoặc (None, lý do)."""
    if enrollment.cohort_id != session.cohort_id:
        return None, 'Học viên không thuộc đợt của buổi học này.'
    att, _ = Attendance.objects.get_or_create(
        tenant=session.tenant, session=session, enrollment=enrollment,
    )
    att.present = present
    att.method = method
    att.checked_in_at = timezone.now() if present else None
    if method == 'manual':
        att.marked_by = user
    att.save()
    return att, None
