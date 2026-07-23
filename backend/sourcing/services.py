import logging

from django.utils import timezone

from .models import Attendance, CohortSession, ContentProgress, Enrollment, Notification, ProgramContent

logger = logging.getLogger(__name__)


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


# ---- Thông báo (M2.5): in-app + email ----

def notification_targets(tenant, restaurant=None, include_user=None):
    """Người nhận thông báo: Admin/OM của tenant (Phòng Đào tạo) + BQL/Trainer của nhà hàng liên
    quan + người tạo đợt."""
    from accounts.models import User

    base = User.objects.filter(tenant=tenant, status=User.Status.ACTIVE)
    users = set(base.filter(role__in=['admin', 'om']))
    if restaurant is not None:
        users |= set(base.filter(role__in=['bql', 'trainer'], restaurant=restaurant))
    if include_user is not None:
        users.add(include_user)
    return [u for u in users if u is not None]


def notify_users(users, title, body='', link='', category=''):
    """Tạo thông báo in-app cho từng user + gửi email (nếu có địa chỉ & đã cấu hình SMTP).
    Lỗi email không làm hỏng request (fail_silently)."""
    from django.conf import settings
    from django.core.mail import send_mail

    seen = set()
    rows = []
    emails = []
    for u in users:
        if u is None or u.id in seen:
            continue
        seen.add(u.id)
        rows.append(Notification(
            tenant=u.tenant, user=u, title=title, body=body, link=link, category=category,
        ))
        addr = (u.email or u.google_email or '').strip()
        if addr:
            emails.append(addr)
    if rows:
        Notification.objects.bulk_create(rows)
    for addr in emails:
        try:
            send_mail(title, body or title, settings.DEFAULT_FROM_EMAIL, [addr], fail_silently=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning('Gửi email thông báo thất bại (%s): %s', addr, exc)
    return len(rows)


def notify_enrollment_added(enrollment):
    cohort = enrollment.cohort
    emp = enrollment.employee
    users = notification_targets(cohort.tenant, restaurant=emp.restaurant, include_user=cohort.created_by)
    notify_users(
        users,
        title=f'Học viên mới trong đợt "{cohort.name}"',
        body=f'{emp.name} ({emp.code}) đã được thêm vào đợt đào tạo "{cohort.name}".',
        link='/sourcing', category='cohort',
    )


def notify_session_created(session):
    cohort = session.cohort
    users = notification_targets(cohort.tenant, include_user=cohort.created_by)
    when = session.date.isoformat() if session.date else ''
    notify_users(
        users,
        title=f'Buổi học mới — đợt "{cohort.name}"',
        body=f'Buổi {session.session_no or ""} {("- " + session.title) if session.title else ""} '
             f'{("ngày " + when) if when else ""}.'.strip(),
        link='/sourcing', category='cohort',
    )


def bulk_enroll_and_invite(cohort, user, filters):
    """C — Lọc nhân sự theo tiêu chí & thêm hàng loạt vào đợt + gửi mời (in-app/email).
    filters: role/restaurant/level_group/operation_unit/position (đều tuỳ chọn) hoặc employee_ids.
    Người nhận thông báo: user có tài khoản khớp tên nhân sự được mời + phòng đào tạo."""
    from employees.models import Employee

    qs = Employee.objects.filter(tenant=cohort.tenant).exclude(
        employee_status=Employee.EmployeeStatus.RESIGNED
    )
    ids = filters.get('employee_ids')
    if ids:
        qs = qs.filter(id__in=ids)
    else:
        if filters.get('restaurant'):
            qs = qs.filter(restaurant_id=filters['restaurant'])
        if filters.get('level_group'):
            qs = qs.filter(level_group__iexact=filters['level_group'])
        if filters.get('operation_unit'):
            qs = qs.filter(operation_unit=filters['operation_unit'])
        if filters.get('position'):
            qs = qs.filter(position__icontains=filters['position'])

    existing = set(
        Enrollment.objects.filter(cohort=cohort).values_list('employee_id', flat=True)
    )
    new_emps = [e for e in qs if e.id not in existing]
    Enrollment.objects.bulk_create([
        Enrollment(tenant=cohort.tenant, cohort=cohort, employee=e, added_by=user)
        for e in new_emps
    ], batch_size=200)

    # Thông báo: khớp nhân sự → user cùng tenant theo full_name (best-effort, vì học viên có thể
    # chưa có tài khoản) + phòng đào tạo.
    from accounts.models import User

    names = {e.name.strip().lower() for e in new_emps}
    matched_users = [
        u for u in User.objects.filter(tenant=cohort.tenant, status=User.Status.ACTIVE)
        if (u.full_name or '').strip().lower() in names
    ]
    targets = set(matched_users) | set(notification_targets(cohort.tenant, include_user=cohort.created_by))
    if new_emps:
        notify_users(
            targets,
            title=f'Mời tham gia đào tạo: {cohort.name}',
            body=f'Bạn/nhân sự của bạn được mời tham gia "{cohort.name}". Quét QR tại buổi học để điểm danh.',
            link='/sourcing', category='cohort',
        )
    return {'invited': len(new_emps), 'already_in': len(existing), 'notified_users': len(matched_users)}


def cohort_report(cohort):
    """Báo cáo tham gia: đối chiếu danh sách mời (enrollment) với có mặt (attendance) theo buổi
    và theo học viên."""
    sessions = list(CohortSession.objects.filter(cohort=cohort).order_by('date', 'session_no'))
    enrollments = list(
        Enrollment.objects.filter(cohort=cohort).select_related('employee', 'employee__restaurant')
    )
    present = {
        (a.session_id, a.enrollment_id)
        for a in Attendance.objects.filter(session__cohort=cohort, present=True)
    }
    session_rows = [
        {
            'session_id': s.id, 'session_no': s.session_no, 'title': s.title,
            'date': s.date.isoformat() if s.date else None,
            'invited': len(enrollments),
            'present': sum(1 for e in enrollments if (s.id, e.id) in present),
        }
        for s in sessions
    ]
    total_sessions = len(sessions) or 1
    people_rows = []
    for e in enrollments:
        attended = sum(1 for s in sessions if (s.id, e.id) in present)
        people_rows.append({
            'employee_code': e.employee.code, 'employee_name': e.employee.name,
            'restaurant_name': e.employee.restaurant.name if e.employee.restaurant else '',
            'attended': attended, 'total_sessions': len(sessions),
            'percent': round(attended / total_sessions * 100),
            'result': e.result, 'status': e.status,
        })
    return {
        'cohort': cohort.name, 'sessions': session_rows, 'people': people_rows,
        'invited_total': len(enrollments),
    }


def notify_enrollment_result(enrollment):
    cohort = enrollment.cohort
    emp = enrollment.employee
    users = notification_targets(cohort.tenant, restaurant=emp.restaurant, include_user=cohort.created_by)
    notify_users(
        users,
        title=f'Kết quả đào tạo — {emp.name}',
        body=f'{emp.name} ({emp.code}) đợt "{cohort.name}": kết quả {enrollment.result}.',
        link='/sourcing', category='cohort',
    )
