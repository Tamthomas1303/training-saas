def normalize_key(value):
    return (value or '').strip().lower()


def matching_checklist_items(employee):
    """Checklist cua 1 nhan su, khop theo Brand (tu restaurant) + Position (normalized).

    Port EmployeeService.gs::_checklistFor - chi Brand + Position, KHONG dung Level_Group
    (giu dung logic ban Apps Script cu).
    """
    from checklist.models import Checklist  # import tre de tranh vong lap luc nap app

    if not employee.restaurant:
        return []
    brand = employee.restaurant.brand
    position_key = normalize_key(employee.position)
    return [
        c for c in Checklist.objects.filter(tenant=employee.tenant, brand=brand).order_by('day', 'order')
        if normalize_key(c.position) == position_key
    ]


def checklist_progress_percent(employee):
    """% tien do dao tao = so checklist da Hoan thanh / tong so checklist khop brand+position."""
    from checklist.models import TrainingProgress

    items = matching_checklist_items(employee)
    if not items:
        return 0
    done_count = TrainingProgress.objects.filter(
        employee=employee,
        checklist_id__in=[c.id for c in items],
        status=TrainingProgress.Status.DONE,
    ).count()
    return round(done_count / len(items) * 100)
