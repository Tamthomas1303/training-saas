"""
Logic nghiep vu module Khoa hoc (MVP Dot 1) - view chi goi ham o day va tra ve, giu view mong
theo dung convention checklist/services.py::save_training_progress.

Dot 3: hoan thanh khoa (Enrollment -> completed) va xac nhan offline goi sang
integration.services (dong bo ho so + xAPI + chung chi) - import CUC BO trong than ham de
tranh vong lap (integration.services co import nguoc lai courses.models, xem docstring file do).
"""
from django.utils import timezone

from employees.models import Employee

from integration.models import OfflineConfirmation

from .models import Course, CourseModule, Enrollment, Lesson, LessonProgress


class ValidationError(Exception):
    pass


def assign_course(user, course, payload):
    """Gan khoa hoc (bulk tao Enrollment) theo danh sach employee_ids HOAC bo loc
    position/restaurant_id/group (level_group). Bo qua nhan su da ghi danh (khong nhan doi -
    unique_together course+employee). Tra ve so nhan su duoc gan MOI."""
    tenant = user.tenant
    employee_ids = payload.get('employee_ids') or []

    if employee_ids:
        employees = Employee.objects.filter(tenant=tenant, id__in=employee_ids)
    else:
        qs = Employee.objects.filter(tenant=tenant)
        position = (payload.get('position') or '').strip()
        restaurant_id = payload.get('restaurant_id')
        group = (payload.get('group') or '').strip()
        if not (position or restaurant_id or group):
            raise ValidationError('Cần chọn nhân sự, hoặc bộ lọc vị trí/nhà hàng/nhóm để gán.')
        if position:
            qs = qs.filter(position=position)
        if restaurant_id:
            qs = qs.filter(restaurant_id=restaurant_id)
        if group:
            qs = qs.filter(level_group=group)
        employees = qs

    existing_ids = set(
        Enrollment.objects.filter(course=course, employee__in=employees)
        .values_list('employee_id', flat=True)
    )
    to_create = [
        Enrollment(tenant=tenant, course=course, employee=e, assigned_by=user)
        for e in employees if e.id not in existing_ids
    ]
    Enrollment.objects.bulk_create(to_create)
    return len(to_create)


def _course_progress_percent(enrollment):
    total = Lesson.objects.filter(module__course_id=enrollment.course_id).count()
    if not total:
        return 0
    done = enrollment.progresses.filter(status=LessonProgress.Status.DONE).count()
    return round(done / total * 100)


def my_courses(employee):
    """Danh sach khoa da ghi danh cua 1 nhan su + % tien do moi khoa (dem lesson done/tong)."""
    enrollments = Enrollment.objects.filter(employee=employee).select_related('course').order_by('-created_at')
    return [
        {
            'enrollment_id': e.id, 'course_id': e.course_id, 'title': e.course.title,
            'cover_url': e.course.cover_url, 'status': e.status,
            'status_display': e.get_status_display(), 'due_date': e.due_date,
            'progress_percent': _course_progress_percent(e),
        }
        for e in enrollments
    ]


def my_course_detail(employee, course_id):
    """Cay chuong->bai + tien do tung bai cho 1 khoa da ghi danh. None neu chua ghi danh."""
    enrollment = (
        Enrollment.objects.filter(employee=employee, course_id=course_id)
        .select_related('course').first()
    )
    if not enrollment:
        return None

    progress_by_lesson = {p.lesson_id: p for p in enrollment.progresses.all()}
    # Dot 3 phan B: nhan "Hoan thanh offline (xac nhan boi X - ngay)" - lay ban ghi
    # OfflineConfirmation MOI NHAT cho tung bai da completed_offline, gom 1 truy van tranh N+1.
    offline_lesson_ids = [
        p.lesson_id for p in progress_by_lesson.values() if p.completed_offline
    ]
    latest_confirmation_by_lesson = {}
    if offline_lesson_ids:
        confirmations = (
            OfflineConfirmation.objects.filter(
                employee=employee, target_type=OfflineConfirmation.TargetType.LESSON,
                target_id__in=offline_lesson_ids,
            )
            .select_related('confirmed_by').order_by('target_id', '-confirmed_at')
        )
        for c in confirmations:
            latest_confirmation_by_lesson.setdefault(c.target_id, c)

    modules = []
    for module in CourseModule.objects.filter(course_id=course_id).prefetch_related('lessons'):
        lessons = []
        for lesson in module.lessons.all():
            progress = progress_by_lesson.get(lesson.id)
            confirmation = latest_confirmation_by_lesson.get(lesson.id)
            lessons.append({
                'id': lesson.id, 'title': lesson.title, 'type': lesson.type,
                'content_url': lesson.content_url, 'content_html': lesson.content_html,
                'duration_sec': lesson.duration_sec, 'anti_seek': lesson.anti_seek,
                'complete_rule': lesson.complete_rule, 'pass_watch_pct': lesson.pass_watch_pct,
                'order': lesson.order,
                'progress': {
                    'status': progress.status if progress else LessonProgress.Status.PENDING,
                    'watched_pct': progress.watched_pct if progress else 0,
                    'last_position_sec': progress.last_position_sec if progress else 0,
                    'completed_at': progress.completed_at if progress else None,
                    'completed_offline': progress.completed_offline if progress else False,
                    'offline_confirmed_by_name': (
                        confirmation.confirmed_by.full_name if confirmation and confirmation.confirmed_by else ''
                    ),
                    'offline_confirmed_at': confirmation.confirmed_at if confirmation else None,
                },
            })
        modules.append({'id': module.id, 'title': module.title, 'order': module.order, 'lessons': lessons})

    return {
        'enrollment_id': enrollment.id, 'course_id': enrollment.course_id,
        'title': enrollment.course.title, 'description': enrollment.course.description,
        'status': enrollment.status, 'progress_percent': _course_progress_percent(enrollment),
        'modules': modules,
    }


def save_lesson_progress(employee, payload):
    """Cap nhat tien do 1 bai: {lesson, watched_pct?, last_position_sec?, mark_done?}. Tu set
    status in_progress/done + completed_at; tu nang Enrollment.status (assigned->in_progress
    khi co bai dau; ->completed khi tat ca bai done). KHONG dong den ho so nhan su (dong bo
    CourseResult la Dot 3)."""
    lesson_id = payload.get('lesson')
    if not lesson_id:
        raise ValidationError('Thiếu lesson')
    lesson = (
        Lesson.objects.filter(id=lesson_id, tenant=employee.tenant)
        .select_related('module').first()
    )
    if not lesson:
        raise ValidationError('Không tìm thấy bài học')

    enrollment = Enrollment.objects.filter(employee=employee, course_id=lesson.module.course_id).first()
    if not enrollment:
        raise ValidationError('Bạn chưa được gán khóa học này')

    progress, progress_created = LessonProgress.objects.get_or_create(
        tenant=employee.tenant, enrollment=enrollment, lesson=lesson,
    )
    if progress_created:
        _log_xapi_safe(employee, 'viewed', 'lesson', lesson.id)

    watched_pct = payload.get('watched_pct')
    last_position_sec = payload.get('last_position_sec')
    mark_done = bool(payload.get('mark_done'))

    if watched_pct is not None:
        progress.watched_pct = max(0, min(100, int(watched_pct)))
    if last_position_sec is not None:
        progress.last_position_sec = max(0, int(last_position_sec))

    became_done = progress.status != LessonProgress.Status.DONE and (
        mark_done or (
            lesson.complete_rule == Lesson.CompleteRule.WATCH_PCT
            and progress.watched_pct >= lesson.pass_watch_pct
        )
    )
    if became_done:
        progress.status = LessonProgress.Status.DONE
        progress.completed_at = timezone.now()
        _log_xapi_safe(employee, 'completed', 'lesson', lesson.id)
    elif progress.status == LessonProgress.Status.PENDING:
        progress.status = LessonProgress.Status.IN_PROGRESS
    progress.save()

    _advance_enrollment_status(enrollment)
    return progress


def _advance_enrollment_status(enrollment):
    """Cap nhat Enrollment.status (assigned->in_progress->completed) theo tien do lesson hien
    tai; ban hanh hook hoan thanh (Dot 3 phan A/C/D) CHI 1 LAN khi vua moi chuyen sang completed
    (khong lap lai neu goi lai cho nguoi da hoan thanh tu truoc). Dung chung boi
    save_lesson_progress va confirm_offline_completion."""
    was_completed = enrollment.status == Enrollment.Status.COMPLETED
    if enrollment.status == Enrollment.Status.ASSIGNED:
        enrollment.status = Enrollment.Status.IN_PROGRESS
    total_lessons = Lesson.objects.filter(module__course_id=enrollment.course_id).count()
    done_lessons = enrollment.progresses.filter(status=LessonProgress.Status.DONE).count()
    if total_lessons and done_lessons >= total_lessons:
        enrollment.status = Enrollment.Status.COMPLETED
    enrollment.save(update_fields=['status', 'updated_at'])

    if enrollment.status == Enrollment.Status.COMPLETED and not was_completed:
        _on_course_completed_safe(enrollment)


def _log_xapi_safe(employee, verb, object_type, object_id):
    """Wrapper cuc bo: log_xapi ban than da tu bat loi, nhung van bao ve them 1 lop o day
    (import tre) de logic Dot 1 (hoc/tien do) khong bao gio bi anh huong boi Dot 3."""
    try:
        from integration.services import log_xapi

        log_xapi(employee, verb, object_type, object_id)
    except Exception:  # noqa: BLE001
        pass


def _on_course_completed_safe(enrollment):
    try:
        from integration.services import on_course_completed

        on_course_completed(enrollment)
    except Exception:  # noqa: BLE001 - hoan thanh khoa (Dot 1) khong duoc phep hong vi Dot 3
        import logging

        logging.getLogger(__name__).exception(
            'on_course_completed thất bại cho enrollment %s - đã bỏ qua, không chặn luồng học.',
            enrollment.id,
        )


def confirm_offline_completion(confirmer, employee, target_type, target_id, method, note='', evidence_url=''):
    """Xac nhan HO 1 bai/khoa da hoan thanh (khong qua player) - Dot 3 phan B. target_type=
    'lesson' -> 1 bai; 'course' -> TOAN BO bai cua khoa (xac nhan ca khoa 1 lan). Tu ghi danh
    (tao Enrollment) neu nhan su chua duoc gan. Ghi 1 OfflineConfirmation/1 bai de audit day du
    (ai xac nhan + khi nao + hinh thuc - bat buoc theo prompt).

    evidence_url: FE (PhotoSlot) gui ve data: URL - can upload len R2 lay URL that truoc khi
    luu (URLField khong chap nhan data: URL), giong quy uoc checklist/evaluation/kpi.services."""
    from checklist.storage import StorageError, is_data_url, upload_data_url

    if evidence_url and is_data_url(evidence_url):
        try:
            evidence_url = upload_data_url(
                evidence_url, f'offline-confirm/{employee.tenant_id}', f'evidence_{employee.id}',
            )
        except StorageError as exc:
            raise ValidationError(str(exc)) from exc

    if target_type == OfflineConfirmation.TargetType.LESSON:
        lesson = Lesson.objects.filter(id=target_id, tenant=employee.tenant).select_related('module').first()
        if not lesson:
            raise ValidationError('Không tìm thấy bài học')
        lessons = [lesson]
        course_id = lesson.module.course_id
    elif target_type == OfflineConfirmation.TargetType.COURSE:
        course = Course.objects.filter(id=target_id, tenant=employee.tenant).first()
        if not course:
            raise ValidationError('Không tìm thấy khóa học')
        lessons = list(Lesson.objects.filter(module__course=course))
        if not lessons:
            raise ValidationError('Khóa học chưa có bài học nào')
        course_id = course.id
    else:
        raise ValidationError('target_type không hợp lệ (cần lesson hoặc course)')

    enrollment, _ = Enrollment.objects.get_or_create(
        tenant=employee.tenant, course_id=course_id, employee=employee,
        defaults={'assigned_by': confirmer},
    )

    for lesson in lessons:
        progress, _ = LessonProgress.objects.get_or_create(
            tenant=employee.tenant, enrollment=enrollment, lesson=lesson,
        )
        if progress.status != LessonProgress.Status.DONE:
            progress.status = LessonProgress.Status.DONE
            progress.completed_at = timezone.now()
        progress.completed_offline = True
        progress.save()
        OfflineConfirmation.objects.create(
            tenant=employee.tenant, target_type=OfflineConfirmation.TargetType.LESSON,
            target_id=lesson.id, employee=employee, confirmed_by=confirmer, method=method,
            note=note, evidence_url=evidence_url,
        )
        _log_xapi_safe(employee, 'confirmed_offline', 'lesson', lesson.id)

    _advance_enrollment_status(enrollment)
    return enrollment


def offline_completion_report(course_id, tenant):
    """Ty le hoan thanh online vs offline (don gian) cho 1 khoa - dem LessonProgress status=done
    trong tat ca Enrollment cua khoa nay."""
    done = LessonProgress.objects.filter(
        tenant=tenant, enrollment__course_id=course_id, status=LessonProgress.Status.DONE,
    )
    offline = done.filter(completed_offline=True).count()
    total = done.count()
    return {
        'total_done': total, 'offline': offline, 'online': total - offline,
        'offline_percent': round(offline / total * 100) if total else 0,
    }


def reorder_items(model, tenant, items):
    """Cap nhat 'order' hang loat cho CourseModule hoac Lesson. items: [{id, order}, ...], chi
    cap nhat ban ghi thuoc dung tenant (an toan, tranh sua cheo tenant)."""
    ids = [item['id'] for item in items]
    by_id = {obj.id: obj for obj in model.objects.filter(tenant=tenant, id__in=ids)}
    updated = []
    for item in items:
        obj = by_id.get(item['id'])
        if obj is None:
            continue
        obj.order = item['order']
        updated.append(obj)
    model.objects.bulk_update(updated, ['order'])
    return len(updated)
