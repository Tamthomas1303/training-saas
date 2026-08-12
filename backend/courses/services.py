"""
Logic nghiep vu module Khoa hoc (MVP Dot 1) - view chi goi ham o day va tra ve, giu view mong
theo dung convention checklist/services.py::save_training_progress.
"""
from django.utils import timezone

from employees.models import Employee

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
    modules = []
    for module in CourseModule.objects.filter(course_id=course_id).prefetch_related('lessons'):
        lessons = []
        for lesson in module.lessons.all():
            progress = progress_by_lesson.get(lesson.id)
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

    progress, _ = LessonProgress.objects.get_or_create(
        tenant=employee.tenant, enrollment=enrollment, lesson=lesson,
    )

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
    elif progress.status == LessonProgress.Status.PENDING:
        progress.status = LessonProgress.Status.IN_PROGRESS
    progress.save()

    if enrollment.status == Enrollment.Status.ASSIGNED:
        enrollment.status = Enrollment.Status.IN_PROGRESS
    total_lessons = Lesson.objects.filter(module__course_id=enrollment.course_id).count()
    done_lessons = enrollment.progresses.filter(status=LessonProgress.Status.DONE).count()
    if total_lessons and done_lessons >= total_lessons:
        enrollment.status = Enrollment.Status.COMPLETED
    enrollment.save(update_fields=['status', 'updated_at'])

    return progress


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
