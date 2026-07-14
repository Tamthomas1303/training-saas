"""So lieu ca nhan cho man Home (Trainer/BQL/AM/KCS). Port TrainingService.gs::listTrainees,
dieu chinh theo quyet dinh khi lam ĐỢT 2 ("Home: DK hoa hong"): dung dung 5 dieu kien hoa hong
thuc te (giong trang Phu cap) thay vi cach tinh nhanh cua ban goc (=so NV dat thu viec x 300k)."""
from .dashboard import _deadline_days_left, _is_pass, scoped_employees
from .services import checklist_progress_percent


def home_payload(user):
    from kpi.models import Commission
    from kpi.services import commission_queryset_for_user

    employees = list(
        scoped_employees(user).exclude(employee_status='resigned').order_by('name')
    )

    eligible_ids = set(
        commission_queryset_for_user(user)
        .filter(status=Commission.Status.ELIGIBLE)
        .values_list('employee_id', flat=True)
    )
    eligible_commissions = commission_queryset_for_user(user).filter(status=Commission.Status.ELIGIBLE)
    commission_amount = float(sum(c.amount for c in eligible_commissions))

    need = 0
    passed15 = 0
    rows = []
    for e in employees:
        progress = checklist_progress_percent(e)
        if progress < 100:
            need += 1
        is_pass = _is_pass(e)
        if is_pass:
            passed15 += 1

        if progress >= 100:
            status = 'done'
        elif progress > 0:
            status = 'in_progress'
        else:
            status = 'not_started'

        days_left = _deadline_days_left(e)
        rows.append({
            'employee_id': e.id, 'name': e.name, 'position': e.position,
            'restaurant': e.restaurant.name if e.restaurant else '',
            'restaurant_id': e.restaurant_id,
            'status': status, 'progress': progress,
            'probation_result': e.final_result, 'is_pass': is_pass,
            'days_left': days_left,
            'commission_eligible': e.id in eligible_ids,
        })

    return {
        'summary': {
            'need': need,
            'passed': passed15,
            'commission_eligible': len(eligible_ids),
            'commission_amount': commission_amount,
        },
        'rows': rows,
    }
