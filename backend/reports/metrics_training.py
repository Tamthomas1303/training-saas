"""Khoi 1 (dao tao nhan su moi) + Khoi 2 (kiem tra kien thuc) cua bao cao dao tao tuan/thang -
tinh toan thang tu DB hien co (Employee/ExamResult), khong qua CSV ngoai."""
from collections import defaultdict


def new_hires_block(tenant, start, end, ref_date):
    """- total_new_hires: NV moi (start_date trong ky) dang lam (khong tinh da nghi).
    - resigned_count: NV chuyen sang nghi viec TRONG KY (Employee.resigned_at, xem
      employees/services.py::change_employee_status).
    - passed_count: NV Pass thu viec TRONG KY (Employee.pass_date).
    - s_level: ty le hoan thanh cap S TINH TU DAU THANG chua ref_date (doc lap voi ky bao
      cao - luon la thang hien tai, dung "tu dau thang" nhu yeu cau, khong phai "trong ky").
    - slow_restaurants: nha hang dang co >=2 NV con thu viec (chua Pass/chua nghi) voi tien
      do checklist TB <50% - snapshot HIEN TAI (khong bound theo ky, vi day la trang thai
      dang dien ra can chu y ngay, khong phai so lieu phat sinh trong ky)."""
    from employees.models import Employee
    from employees.services import batch_checklist_progress_percent

    total_new_hires = (
        Employee.objects.filter(tenant=tenant, start_date__range=(start, end))
        .exclude(employee_status=Employee.EmployeeStatus.RESIGNED)
        .count()
    )
    resigned_count = Employee.objects.filter(tenant=tenant, resigned_at__range=(start, end)).count()
    passed_count = Employee.objects.filter(tenant=tenant, pass_date__range=(start, end)).count()

    month_start = ref_date.replace(day=1)
    s_level_qs = (
        Employee.objects.filter(tenant=tenant, level_group__iexact='S', start_date__range=(month_start, ref_date))
        .exclude(employee_status=Employee.EmployeeStatus.RESIGNED)
    )
    s_level_total = s_level_qs.count()
    s_level_passed = s_level_qs.filter(final_result='Pass thử việc').count()
    s_level_rate = round(s_level_passed / s_level_total * 100, 1) if s_level_total else None

    probation_qs = list(
        Employee.objects.filter(
            tenant=tenant, employee_status=Employee.EmployeeStatus.PROBATION, restaurant__isnull=False,
        ).select_related('restaurant')
    )
    progress_by_id = batch_checklist_progress_percent(probation_qs) if probation_qs else {}
    by_restaurant = defaultdict(list)
    for e in probation_qs:
        by_restaurant[e.restaurant].append(progress_by_id.get(e.id, 0))

    slow_restaurants = []
    for restaurant, percents in by_restaurant.items():
        if len(percents) < 2:
            continue
        avg = sum(percents) / len(percents)
        if avg < 50:
            slow_restaurants.append({'restaurant': restaurant.name, 'count': len(percents), 'avg_percent': round(avg, 1)})
    slow_restaurants.sort(key=lambda r: r['avg_percent'])

    return {
        'total_new_hires': total_new_hires,
        'resigned_count': resigned_count,
        'passed_count': passed_count,
        's_level_total': s_level_total,
        's_level_passed': s_level_passed,
        's_level_rate': s_level_rate,
        'slow_restaurants': slow_restaurants,
    }


EXAM_PASS_THRESHOLD = 80
EXAM_BUCKETS = (
    ('xuat_sac', 'Xuất sắc (≥90)', 90, None),
    ('gioi', 'Giỏi (85 - <90)', 85, 90),
    ('trung_binh', 'Trung bình (80 - <85)', 80, 85),
    ('yeu', 'Yếu (<80)', None, 80),
)


def exam_block(tenant, start, end):
    """Loc ExamResult theo exam_date (ngay thi that su, xem sync_cls.py::_parse_exam_date)
    trong ky, dung final_score (uu tien diem phuc khao). Phan loai + ty le dat tinh theo
    LUOT THI (attempt), khong phai theo nguoi."""
    from django.db.models.functions import Coalesce

    from cls_sync.models import ExamResult

    scores = list(
        ExamResult.objects.filter(tenant=tenant, exam_date__range=(start, end))
        .annotate(computed_score=Coalesce('score_adjusted', 'score'))
        .exclude(computed_score__isnull=True)
        .values_list('employee_id', 'computed_score')
    )
    total_attempts = len(scores)
    if not total_attempts:
        return {
            'total_attempts': 0, 'distinct_people': 0, 'pass_rate': None, 'avg_score': None,
            'classification': [
                {'key': key, 'label': label, 'count': 0, 'percent': 0} for key, label, _, _ in EXAM_BUCKETS
            ],
        }

    distinct_people = len({row[0] for row in scores})
    values = [float(row[1]) for row in scores]
    avg_score = round(sum(values) / total_attempts, 1)
    pass_count = sum(1 for v in values if v >= EXAM_PASS_THRESHOLD)
    pass_rate = round(pass_count / total_attempts * 100, 1)

    classification = []
    for key, label, low, high in EXAM_BUCKETS:
        if low is not None and high is not None:
            count = sum(1 for v in values if low <= v < high)
        elif low is not None:
            count = sum(1 for v in values if v >= low)
        else:
            count = sum(1 for v in values if v < high)
        classification.append({
            'key': key, 'label': label, 'count': count,
            'percent': round(count / total_attempts * 100, 1),
        })

    return {
        'total_attempts': total_attempts,
        'distinct_people': distinct_people,
        'pass_rate': pass_rate,
        'avg_score': avg_score,
        'classification': classification,
    }
