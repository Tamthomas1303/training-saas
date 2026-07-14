"""So lieu Dashboard (Admin/Training/OM/BOD). Port Api.gs::api_dashboardStats + ReportService.gs.

Cac tram gian hoa da ghi chu tai tung ham (khac voi ban goc o cho can, giu nguyen cong thuc
o cho co the).
"""
import datetime
from collections import defaultdict

from django.conf import settings
from django.utils import timezone

from checklist.models import TrainingProgress

from .models import Employee
from .permissions import get_restaurant_scope
from .services import checklist_progress_percent, normalize_key


def scoped_employees(user):
    qs = Employee.objects.filter(tenant=user.tenant).select_related('restaurant', 'trainer')
    scope = get_restaurant_scope(user)
    if not scope['all']:
        qs = qs.filter(restaurant_id__in=scope['restaurant_ids'])
    return qs


def _is_pass(employee):
    text = (employee.final_result or '').lower()
    return ('pass' in text or 'đạt' in text) and 'không đạt' not in text


def _is_fail(employee):
    return 'không đạt' in (employee.final_result or '').lower()


def _probation_days(employee):
    if employee.probation_days:
        return employee.probation_days
    return settings.PROBATION_O_DAYS if (employee.level_group or '').upper() == 'O' else settings.PROBATION_S_DAYS


def _deadline_days_left(employee):
    days = _probation_days(employee)
    if not employee.start_date or not days:
        return None
    deadline = employee.start_date + datetime.timedelta(days=days)
    return (deadline - timezone.now().date()).days


def dashboard_stats(user):
    employees = list(scoped_employees(user))
    today = timezone.now().date()

    new_this = [e for e in employees if e.start_date and e.start_date.month == today.month and e.start_date.year == today.year]
    prev_month_date = (today.replace(day=1) - datetime.timedelta(days=1))
    new_prev = [
        e for e in employees
        if e.start_date and e.start_date.month == prev_month_date.month and e.start_date.year == prev_month_date.year
    ]
    total_new_delta = (
        round((len(new_this) - len(new_prev)) / len(new_prev) * 100) if len(new_prev) else None
    )

    passed = [e for e in employees if _is_pass(e)]
    failed = [e for e in employees if _is_fail(e)]
    decided = passed + failed
    pass_rate = round(len(passed) / len(decided) * 100) if decided else 0

    probation_now = [e for e in employees if e.employee_status == Employee.EmployeeStatus.PROBATION]

    return {
        'total_new': len(new_this),
        'total_new_delta': total_new_delta,
        'probation': len(probation_now),
        'completed': len(passed),
        'pass_rate': pass_rate,
        'generated_at': timezone.now().isoformat(),
    }


def recent_progress(user, limit=12):
    employees = list(
        scoped_employees(user).exclude(employee_status=Employee.EmployeeStatus.RESIGNED)
        .order_by('-start_date')[:limit]
    )
    return [
        {'employee_id': e.id, 'name': e.name, 'position': e.position, 'progress': checklist_progress_percent(e)}
        for e in employees
    ]


def top_trainer(user):
    employees = [e for e in scoped_employees(user) if _is_pass(e) and e.trainer_id]
    counts = defaultdict(int)
    for e in employees:
        counts[e.trainer_id] += 1
    if not counts:
        return None
    best_id = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    trainer = next((e.trainer for e in employees if e.trainer_id == best_id), None)
    if not trainer:
        return None
    return {'user_id': trainer.id, 'name': trainer.full_name or trainer.username, 'trained': counts[best_id]}


def deadlines(user, limit=8):
    warn = settings.PROBATION_DEADLINE_WARN_DAYS
    rows = []
    for e in scoped_employees(user).filter(employee_status=Employee.EmployeeStatus.PROBATION):
        days_left = _deadline_days_left(e)
        if days_left is None or days_left > warn:
            continue
        rows.append({
            'employee_id': e.id, 'name': e.name, 'position': e.position,
            'restaurant': e.restaurant.name if e.restaurant else '', 'days_left': days_left,
        })
    rows.sort(key=lambda r: r['days_left'])
    return rows[:limit]


def by_brand(user):
    counts = defaultdict(int)
    for e in scoped_employees(user).exclude(employee_status=Employee.EmployeeStatus.RESIGNED):
        brand = (e.restaurant.brand if e.restaurant else '') or 'Khác'
        counts[brand] += 1
    return sorted(
        ({'brand': b, 'count': n} for b, n in counts.items()),
        key=lambda x: x['count'], reverse=True,
    )


FULLTIME_S_EXCLUDE_KEYWORDS = ('tts', 'thực tập', 'thời vụ', 'cộng tác', 'part')


def _is_fulltime_s(employee):
    if (employee.level_group or '').upper() != 'S':
        return False
    text = normalize_key((employee.position or '') + ' ' + (employee.job_level or ''))
    return not any(k in text for k in FULLTIME_S_EXCLUDE_KEYWORDS)


def _completion_date(employee):
    last = (
        TrainingProgress.objects.filter(employee=employee, status=TrainingProgress.Status.DONE)
        .order_by('-completed_at').first()
    )
    return last.completed_at.date() if last and last.completed_at else None


def probation15(user):
    """Ty le hoan thanh thu viec <=15 ngay (cap S full-time). Port ReportService.gs::probation15."""
    today = timezone.now().date()
    d15 = settings.PROBATION_S_DAYS
    by_restaurant = defaultdict(lambda: {'num': 0, 'den': 0, 'name': ''})
    total_num = total_den = 0

    for e in scoped_employees(user):
        if not _is_fulltime_s(e) or not e.start_date:
            continue
        if (today - e.start_date).days < d15:
            continue  # chua den han 15 ngay - chua tinh
        rid = e.restaurant_id or 0
        by_restaurant[rid]['den'] += 1
        by_restaurant[rid]['name'] = e.restaurant.name if e.restaurant else 'Khác'
        total_den += 1
        completed = _completion_date(e)
        on_schedule = _is_pass(e) and completed and (completed - e.start_date).days <= d15
        if on_schedule:
            by_restaurant[rid]['num'] += 1
            total_num += 1

    rate = round(total_num / total_den * 100) if total_den else 0
    return {
        'rate': rate, 'num': total_num, 'den': total_den,
        'by_restaurant': [
            {'restaurant_id': rid, 'restaurant_name': v['name'], 'num': v['num'], 'den': v['den']}
            for rid, v in by_restaurant.items()
        ],
    }


def allowance_cost(user):
    """Chi phi phu cap trainer - tong Amount cua cac ban ghi Commission dang ELIGIBLE trong
    pham vi user. Port ReportService.gs::allowanceCost (delegate CommissionService.list)."""
    from kpi.models import Commission
    from kpi.services import commission_queryset_for_user

    total = commission_queryset_for_user(user).filter(status=Commission.Status.ELIGIBLE).count()
    qs = commission_queryset_for_user(user).filter(status=Commission.Status.ELIGIBLE)
    return float(sum(c.amount for c in qs)) if total else 0.0


def dashboard_payload(user):
    return {
        'stats': dashboard_stats(user),
        'recent': recent_progress(user),
        'top_trainer': top_trainer(user),
        'deadlines': deadlines(user),
        'by_brand': by_brand(user),
        'prob15': probation15(user),
        'allowance_cost': allowance_cost(user),
    }
