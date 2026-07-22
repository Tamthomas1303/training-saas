from django.utils import timezone

from .models import Attendance, CohortSession, ContentProgress, Enrollment, ProgramContent


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


def enrollment_contents(enrollment):
    """Checklist nội dung của chương trình + trạng thái hoàn thành của học viên này."""
    contents = ProgramContent.objects.filter(program=enrollment.cohort.program).order_by('order')
    done_by_content = {
        p.content_id: p for p in ContentProgress.objects.filter(enrollment=enrollment)
    }
    rows = []
    for c in contents:
        p = done_by_content.get(c.id)
        rows.append({
            'content_id': c.id,
            'session_no': c.session_no,
            'topic': c.topic,
            'content': c.content,
            'doc_url': c.doc_url,
            'done': bool(p and p.done),
        })
    return rows


def toggle_content(enrollment, content, done):
    """Đánh dấu 1 mục nội dung hoàn thành/chưa cho học viên."""
    if content.program_id != enrollment.cohort.program_id:
        return None, 'Mục nội dung không thuộc chương trình của đợt này.'
    prog, _ = ContentProgress.objects.get_or_create(
        tenant=enrollment.tenant, enrollment=enrollment, content=content,
    )
    prog.done = done
    prog.completed_at = timezone.now() if done else None
    prog.save()
    return prog, None


def enrollment_summary(enrollment):
    """Tóm tắt để chốt kết quả: % điểm danh + % nội dung hoàn thành."""
    session_total = CohortSession.objects.filter(cohort=enrollment.cohort).count()
    attended = Attendance.objects.filter(enrollment=enrollment, present=True).count()
    content_total = ProgramContent.objects.filter(program=enrollment.cohort.program).count()
    content_done = ContentProgress.objects.filter(enrollment=enrollment, done=True).count()
    return {
        'session_total': session_total,
        'attended': attended,
        'attendance_percent': round(attended / session_total * 100) if session_total else 0,
        'content_total': content_total,
        'content_done': content_done,
        'content_percent': round(content_done / content_total * 100) if content_total else 0,
    }


def finalize_enrollment(enrollment, result):
    """Chốt kết quả học viên: Đạt → completed, Không đạt → failed."""
    if result not in ('Đạt', 'Không đạt'):
        return None, 'Kết quả không hợp lệ (Đạt / Không đạt).'
    enrollment.result = result
    enrollment.status = (
        Enrollment.Status.COMPLETED if result == 'Đạt' else Enrollment.Status.FAILED
    )
    enrollment.completed_at = timezone.now()
    enrollment.save(update_fields=['result', 'status', 'completed_at'])
    return enrollment, None
