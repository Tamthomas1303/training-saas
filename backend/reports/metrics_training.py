"""Khoi 1 (dao tao nhan su moi) + Khoi 2 (kiem tra kien thuc) cua bao cao dao tao tuan/thang -
tinh toan thang tu DB hien co (Employee/ExamResult), khong qua CSV ngoai."""
import datetime
from collections import defaultdict


def _s_level_stats(tenant, month_start, month_end):
    """Cong thuc probationSMonth (port Apps Script): cap S (level_group='S') co start_date
    TRONG THANG (month_start..month_end, KHONG chan o ref_date de "trong thang" nhat quan du
    chay giua thang), loai nghi viec, loai khoi van phong/bep trung tam (operation_unit=OFFICE
    - 2 nhan hien thi nay gop chung vao 1 enum OFFICE, xem employees/recruitment.py::
    _map_operation_unit), va loai "danh gia roi sang thang sau" (start_date + so ngay thu viec
    > cuoi thang - se tinh vao thang ke tiep). Tu so/mau so deu tinh tren CUNG tap da loc nay."""
    from employees.dashboard import _probation_days
    from employees.models import Employee

    cohort = (
        Employee.objects.filter(tenant=tenant, level_group__iexact='S', start_date__range=(month_start, month_end))
        .exclude(employee_status=Employee.EmployeeStatus.RESIGNED)
        .exclude(operation_unit=Employee.OperationUnit.OFFICE)
    )
    total = passed = 0
    for e in cohort:
        deadline = e.start_date + datetime.timedelta(days=_probation_days(e))
        if deadline > month_end:
            continue  # danh gia roi sang thang sau - tinh vao thang ke tiep
        total += 1
        if e.final_result == 'Pass thử việc':
            passed += 1
    rate = round(passed / total * 100, 1) if total else None
    return total, passed, rate


def _company_eval_days(employee):
    """So ngay thu viec dung RIENG cho company_rate (probationCompanyMonth): uu tien
    employee.probation_days neu co; neu khong, cap S (level_group='S') = PROBATION_S_DAYS,
    CON LAI (O/van phong/PT dai han) = PROBATION_O_DAYS. Khac voi employees/dashboard.py::
    _probation_days o CHIEU MAC DINH khi level_group rong/khong xac dinh: ham do mac dinh ve
    S (15 ngay) tru khi ro rang la 'O'; ham nay mac dinh ve O (60 ngay) tru khi ro rang la 'S'
    - dung theo dung dac ta "con lai = 60 ngay" cua khoi company_rate (khong dung chung voi
    _probation_days vi 2 cong thuc co the ra ket qua khac nhau voi nhan su chua gan level_group)."""
    from django.conf import settings

    if employee.probation_days:
        return employee.probation_days
    is_level_s = (employee.level_group or '').upper() == 'S'
    return settings.PROBATION_S_DAYS if is_level_s else settings.PROBATION_O_DAYS


def _company_stats(tenant, month_start, month_end):
    """Cong thuc probationCompanyMonth (port Apps Script): TOAN BO nhan su (khong loc level/
    khoi), mau so = so NV co NGAY DANH GIA (eval_date = start_date + so ngay thu viec, xem
    _company_eval_days) roi TRONG THANG nay, da loai nghi viec. Tu so = trong do da Pass."""
    from django.conf import settings
    from employees.models import Employee

    # eval_date toi da cach start_date PROBATION_O_DAYS (muc mac dinh dai nhat) - xet ung vien
    # co start_date tu (month_start - PROBATION_O_DAYS) den month_end de khong bo sot ai co
    # eval_date roi dung trong thang.
    earliest_start = month_start - datetime.timedelta(days=settings.PROBATION_O_DAYS)
    candidates = (
        Employee.objects.filter(tenant=tenant, start_date__range=(earliest_start, month_end))
        .exclude(employee_status=Employee.EmployeeStatus.RESIGNED)
    )
    total = passed = 0
    for e in candidates:
        eval_date = e.start_date + datetime.timedelta(days=_company_eval_days(e))
        if not (month_start <= eval_date <= month_end):
            continue
        total += 1
        if e.final_result == 'Pass thử việc':
            passed += 1
    rate = round(passed / total * 100, 1) if total else None
    return total, passed, rate


def new_hires_block(tenant, start, end, ref_date):
    """- total_new_hires: NV moi (start_date trong ky) dang lam (khong tinh da nghi).
    - resigned_count: NV chuyen sang nghi viec TRONG KY (Employee.resigned_at, xem
      employees/services.py::change_employee_status).
    - passed_count: NV Pass thu viec TRONG KY (Employee.pass_date).
    - s_level: ty le hoan thanh cap S TRONG THANG (thang chua ref_date - xem _s_level_stats).
    - company: ty le hoan thanh thu viec TOAN CONG TY TRONG THANG, tinh theo ngay danh gia
      (khong loc level/khoi - xem _company_stats).
    - slow_restaurants: nha hang dang co >=2 NV con thu viec (chua Pass/chua nghi, loai khoi
      van phong/bep trung tam) voi tien do checklist TB <50% - snapshot HIEN TAI (khong bound
      theo ky, vi day la trang thai dang dien ra can chu y ngay, khong phai so lieu phat sinh
      trong ky)."""
    from employees.models import Employee
    from employees.services import batch_checklist_progress_percent

    total_new_hires = (
        Employee.objects.filter(tenant=tenant, start_date__range=(start, end))
        .exclude(employee_status=Employee.EmployeeStatus.RESIGNED)
        .count()
    )
    resigned_count = Employee.objects.filter(tenant=tenant, resigned_at__range=(start, end)).count()
    passed_count = Employee.objects.filter(tenant=tenant, pass_date__range=(start, end)).count()

    from .period import _last_day_of_month

    month_start = ref_date.replace(day=1)
    month_end = _last_day_of_month(ref_date)

    s_level_total, s_level_passed, s_level_rate = _s_level_stats(tenant, month_start, month_end)
    company_total, company_passed, company_rate = _company_stats(tenant, month_start, month_end)

    probation_qs = list(
        Employee.objects.filter(
            tenant=tenant, employee_status=Employee.EmployeeStatus.PROBATION, restaurant__isnull=False,
        )
        .exclude(operation_unit=Employee.OperationUnit.OFFICE)
        .select_related('restaurant')
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
        'company_total': company_total,
        'company_passed': company_passed,
        'company_rate': company_rate,
        'slow_restaurants': slow_restaurants,
    }


EXAM_PASS_THRESHOLD = 80
EXAM_BUCKETS = (
    ('xuat_sac', 'Xuất sắc (≥90)', 90, None),
    ('gioi', 'Giỏi (85 - <90)', 85, 90),
    ('trung_binh', 'Trung bình (80 - <85)', 80, 85),
    ('yeu', 'Yếu (<80)', None, 80),
)


def exam_block(tenant, start, end, restaurant_id=None):
    """Loc ExamResult theo exam_date (ngay thi that su, xem sync_cls.py::_parse_exam_date)
    trong ky, dung final_score (uu tien diem phuc khao). Phan loai + ty le dat tinh theo
    LUOT THI (attempt), khong phai theo nguoi. restaurant_id (tuy chon) - loc them theo
    Employee.restaurant cua nguoi thi (dung cho man tong hop CEO/GDDT loc theo nha hang)."""
    from django.db.models.functions import Coalesce

    from cls_sync.models import ExamResult

    qs = ExamResult.objects.filter(tenant=tenant, exam_date__range=(start, end))
    if restaurant_id:
        qs = qs.filter(employee__restaurant_id=restaurant_id)
    scores = list(
        qs.annotate(computed_score=Coalesce('score_adjusted', 'score'))
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
