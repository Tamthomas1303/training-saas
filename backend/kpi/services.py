import datetime
from collections import defaultdict

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import User
from checklist.storage import StorageError, is_data_url, upload_data_url, upload_pdf_bytes
from employees.dashboard import scoped_employees
from employees.models import Employee
from employees.permissions import can_access_restaurant, get_restaurant_scope
from employees.services import probation_conditions, trainer_of
from restaurants.models import Restaurant

from .models import Commission, ExportedReport, KpiParticipant, KpiSession
from .pdf import build_allowance_pdf, build_kpi_report_pdf, build_kpi_session_pdf


class ValidationError(Exception):
    pass


def save_kpi_session(user, payload):
    """Ghi 1 buoi KPI dao tao. Port KPIService.gs::saveSession: bat buoc du 3 anh (tai lieu/
    ly thuyet/thuc hanh) + moi nguoi tham gia phai ky, kiem tra quyen truy cap nha hang."""
    tenant = user.tenant

    restaurant_id = payload.get('restaurant') or user.restaurant_id
    if not restaurant_id:
        raise ValidationError('Chọn nhà hàng tổ chức buổi đào tạo.')
    if not can_access_restaurant(user, int(restaurant_id)):
        raise ValidationError('Không đủ quyền tổ chức đào tạo tại nhà hàng này.')

    restaurant = Restaurant.objects.filter(pk=restaurant_id, tenant=tenant).first()
    if not restaurant:
        raise ValidationError('Không tìm thấy nhà hàng')

    topic = (payload.get('topic') or '').strip()
    if not topic:
        raise ValidationError('Vui lòng chọn chủ đề đào tạo (theo tài liệu chuẩn)')

    date = parse_date(payload.get('date') or '')
    if not date:
        raise ValidationError('Thiếu ngày đào tạo')

    participants_payload = payload.get('participants') or []
    if not participants_payload:
        raise ValidationError('Cần ít nhất 1 nhân viên tham gia')

    img1 = payload.get('img_tailieu')
    img2 = payload.get('img_lythuyet')
    img3 = payload.get('img_thuchanh')
    if not img1 or not img2 or not img3:
        raise ValidationError('Cần đủ 3 ảnh: ảnh tài liệu, ảnh lý thuyết, ảnh thực hành.')

    missing_sign = [p for p in participants_payload if not p.get('sign')]
    if missing_sign:
        raise ValidationError(
            f'Mỗi nhân sự tham gia phải ký xác nhận (còn thiếu {len(missing_sign)} chữ ký).'
        )

    folder = f'evidence/{tenant.id}/kpi'
    uploaded = {}
    for key, value in [('img_tailieu', img1), ('img_lythuyet', img2), ('img_thuchanh', img3)]:
        if is_data_url(value):
            try:
                uploaded[key] = upload_data_url(value, folder, key)
            except StorageError as exc:
                raise ValidationError(str(exc)) from exc
        else:
            uploaded[key] = value

    session = KpiSession.objects.create(
        tenant=tenant,
        restaurant=restaurant,
        trainer=user,
        topic=topic,
        document_id=payload.get('document') or None,
        date=date,
        note=payload.get('note', '') or '',
        img_tailieu=uploaded['img_tailieu'],
        img_lythuyet=uploaded['img_lythuyet'],
        img_thuchanh=uploaded['img_thuchanh'],
    )

    participant_rows = []
    for p in participants_payload:
        employee = Employee.objects.filter(pk=p.get('employee'), tenant=tenant).first()
        if not employee:
            continue
        sign_value = p.get('sign')
        if is_data_url(sign_value):
            try:
                sign_url = upload_data_url(
                    sign_value, f'signatures/{tenant.id}', f'kpisign_{session.id}_{employee.id}'
                )
            except StorageError as exc:
                raise ValidationError(str(exc)) from exc
        else:
            sign_url = sign_value
        participant_rows.append(KpiParticipant(
            tenant=tenant, session=session, employee=employee, sign_url=sign_url,
        ))
    KpiParticipant.objects.bulk_create(participant_rows)

    pdf_bytes = build_kpi_session_pdf({
        'record_no': f'KPI{session.id}/{session.date.year}',
        'tenant_name': tenant.name,
        'restaurant': restaurant.name,
        'topic': topic,
        'date': session.date.strftime('%d/%m/%Y'),
        'trainer_name': user.full_name or user.username,
        'images': {
            'tai_lieu': session.img_tailieu,
            'ly_thuyet': session.img_lythuyet,
            'thuc_hanh': session.img_thuchanh,
        },
        'participants': [
            {'name': row.employee.name, 'position': row.employee.position, 'sign_url': row.sign_url}
            for row in participant_rows
        ],
    })
    try:
        pdf_url = upload_pdf_bytes(pdf_bytes, f'bienban/{tenant.id}', f'BienBanKPI_{session.id}')
    except StorageError as exc:
        raise ValidationError(str(exc)) from exc
    session.pdf_url = pdf_url
    session.save(update_fields=['pdf_url'])

    return session


def kpi_queryset_for_user(user):
    qs = KpiSession.objects.filter(tenant=user.tenant)
    scope = get_restaurant_scope(user)
    if not scope['all']:
        qs = qs.filter(restaurant_id__in=scope['restaurant_ids'])
    return qs


def kpi_stats(user):
    """Thong ke cho man dashboard KPI. Port KPIService.gs::adminKPI. Ban goc khong loc theo
    pham vi nha hang trong ham nay (tat ca session); o day toi ap dung scope de tranh lo du
    lieu nha hang khac cho AM/KCS/BQL - chat hon ban goc nhung hop ly cho da-tenant."""
    sessions = list(kpi_queryset_for_user(user).select_related('restaurant'))
    participant_count = KpiParticipant.objects.filter(session__in=sessions).count()

    total_classes = len(sessions)
    total_joins = participant_count
    avg_per_class = round(total_joins / total_classes, 1) if total_classes else 0

    topic_count = defaultdict(int)
    for s in sessions:
        topic_count[s.topic or '(không tên)'] += 1
    top_topics = sorted(
        ({'topic': t, 'count': n} for t, n in topic_count.items()),
        key=lambda x: x['count'], reverse=True,
    )[:10]

    now = timezone.now()
    by_restaurant = defaultdict(set)
    for s in sessions:
        if s.date.month == now.month and s.date.year == now.year:
            by_restaurant[s.restaurant_id].add(s.date.isoformat())

    target = settings.KPI_TARGET_PER_MONTH
    per_restaurant = [
        {
            'restaurant_id': rid,
            'restaurant_name': next((s.restaurant.name for s in sessions if s.restaurant_id == rid), ''),
            'done': len(days),
            'target': target,
            'achieved': len(days) >= target,
        }
        for rid, days in by_restaurant.items()
    ]

    return {
        'total_classes': total_classes,
        'total_joins': total_joins,
        'avg_per_class': avg_per_class,
        'top_topics': top_topics,
        'per_restaurant': per_restaurant,
    }


def recompute_commission(employee):
    """Tinh lai hoa hong cho 1 nhan su. Port CommissionService.gs::recompute."""
    tenant = employee.tenant
    allowlist = settings.COMMISSION_RESTAURANT_ALLOWLIST

    existing = Commission.objects.filter(employee=employee).first()

    if allowlist and (not employee.restaurant or employee.restaurant.code not in allowlist):
        if existing and existing.status != Commission.Status.PAID:
            existing.status = Commission.Status.NA
            existing.save(update_fields=['status', 'updated_at'])
        return existing

    trainer = trainer_of(employee)
    if not trainer or trainer.role != User.Role.TRAINER:
        if existing and existing.status != Commission.Status.PAID:
            existing.status = Commission.Status.NA
            existing.save(update_fields=['status', 'updated_at'])
        return existing

    conditions = probation_conditions(employee)
    today = timezone.now().date()
    in_retrain = bool(employee.retrain_deadline and employee.retrain_deadline >= today)

    if in_retrain:
        status = Commission.Status.RETRAIN
    elif conditions['all_pass'] and conditions['worked_1month']:
        status = Commission.Status.ELIGIBLE
    else:
        status = Commission.Status.WAITING

    commission = existing or Commission(tenant=tenant, employee=employee)

    if commission.pk and commission.status == Commission.Status.PAID:
        status = Commission.Status.PAID  # sticky - da chi thi giu nguyen

    commission.trainer = trainer
    commission.amount = settings.COMMISSION_AMOUNT
    commission.cond_lms = conditions['lms']
    commission.cond_exam = conditions['exam']
    commission.cond_training = conditions['training']
    commission.cond_skill_eval = conditions['skill_pass']
    commission.cond_worked_1month = conditions['worked_1month']
    commission.status = status
    commission.retrain_deadline = employee.retrain_deadline
    commission.month = today.month
    commission.year = today.year
    commission.save()
    return commission


def recompute_all_commissions(tenant):
    processed = 0
    for employee in Employee.objects.filter(tenant=tenant):
        try:
            recompute_commission(employee)
            processed += 1
        except Exception:
            continue
    return processed


def commission_queryset_for_user(user):
    qs = Commission.objects.filter(tenant=user.tenant).exclude(status=Commission.Status.NA)
    scope = get_restaurant_scope(user)
    if not scope['all']:
        qs = qs.filter(employee__restaurant_id__in=scope['restaurant_ids'])
    return qs.select_related('employee', 'trainer')


def mark_commission_paid(commission):
    commission.status = Commission.Status.PAID
    commission.save(update_fields=['status', 'updated_at'])
    return commission


def _kpi_tier_days(position):
    """Han "dung lo trinh" theo vi tri. Port KpiReportService.gs::TIER (S=15, O2=30, O3=60)."""
    p = (position or '').lower()
    if 'giám sát' in p or 'bếp phó' in p:
        return 30
    if 'quản lý' in p or 'bếp trưởng' in p:
        return 60
    return 15


def _is_parttime_p(employee):
    letter = (employee.job_level or '').strip().upper()[:1]
    level = letter if letter in ('S', 'O', 'P') else (employee.level_group or '').upper()
    return level == 'P'


def _strip_diacritics(text):
    """Chuan hoa NFD + loai dau + doi d/Đ -> d + lowercase - dung de so khop Job_Position (vd
    'NV Cơm gà' can khop tu khoa 'com ga'). Chuoi CON DAU se lam .find()/'in' truot (Phan 1
    muc 7 - "QUAN TRONG ve so khop tieng Viet")."""
    import unicodedata

    text = unicodedata.normalize('NFD', text or '')
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    return text.replace('Đ', 'D').replace('đ', 'd').lower()


# Tu khoa nhan dien nhan su bep (BOH) - KHONG chi chu "bep", con co cac vi tri khong chua chu
# nay nhu "NV Com ga"/"To Truong Thot"/"Salad"/"Chao"/"Food check" (Phan 1 muc 7).
BOH_KEYWORDS = ('bep', 'thot', 'com ga', 'salad', 'chao', 'food check')


def _is_boh_position(position):
    normalized = _strip_diacritics(position)
    return any(kw in normalized for kw in BOH_KEYWORDS)


def _bql_cohort_stats(employees, month, year):
    """Cohort BQL KPI (port Apps Script 05-07/08/2026): nhan su co HAN DANH GIA (start_date +
    so ngay theo cap - xem _kpi_tier_days) roi TRONG ky bao cao, VA thuoc Khoi Nha hang
    (operation_unit='restaurant' - LOAI HAN Khoi Van phong/San xuat va nhan su khong co phong
    ban, ho khong xuat hien o bat ky dau trong bao cao nay). Loai khoi mau/tu so: nghi viec,
    part-time cap P (Job_Level bat dau 'P' hoac level_group='P'). 'Dung lo trinh' do bang
    pass_date (KHONG dung moc hoan thanh checklist, vi dau Pass co the dong muon). 'Dat ky nang
    lan dau' = trong cohort, lay danh gia Skill_BQL SOM NHAT cua moi nguoi (khong gioi han
    thang danh gia) - mau = so nguoi da co danh gia, tu = so nguoi co ket qua bai DAU TIEN la
    Dat.

    Nha hang van xuat hien du cohort = 0/0, kem so nhan su bi loai (excl_resigned/
    excl_next_period) cho nhung nguoi VAO TRONG KY nay nhung nghi viec hoac han danh gia roi
    sang ky sau - de bao cao khong "bien mat" nha hang do."""
    from evaluation.models import Evaluation

    by_restaurant = {}

    def _row(e):
        rid = e.restaurant_id or 0
        return by_restaurant.setdefault(rid, {
            'restaurant': e.restaurant.name if e.restaurant else 'Khác',
            'brand': e.restaurant.brand if e.restaurant else '',
            'on_num': 0, 'on_den': 0, 'skill_pass': 0, 'skill_total': 0,
            'excl_resigned': 0, 'excl_next_period': 0,
        })

    cohort = []
    for e in employees:
        if not e.start_date or e.operation_unit != Employee.OperationUnit.RESTAURANT:
            continue
        tier = _kpi_tier_days(e.position)
        deadline = e.start_date + datetime.timedelta(days=tier)
        in_period = deadline.month == month and deadline.year == year
        hired_this_period = e.start_date.month == month and e.start_date.year == year
        resigned = e.employee_status == Employee.EmployeeStatus.RESIGNED

        if in_period:
            if resigned:
                _row(e)['excl_resigned'] += 1
                continue
            if _is_parttime_p(e):
                continue
            row = _row(e)
            row['on_den'] += 1
            cohort.append(e)
            on_track = bool(e.pass_date) and (e.pass_date - e.start_date).days <= tier
            if on_track:
                row['on_num'] += 1
        elif hired_this_period:
            if resigned:
                _row(e)['excl_resigned'] += 1
            elif not _is_parttime_p(e):
                _row(e)['excl_next_period'] += 1

    for e in cohort:
        first_eval = (
            Evaluation.objects.filter(employee=e, eval_type='Skill_BQL', status='done')
            .order_by('date', 'completed_at', 'id').first()
        )
        if not first_eval:
            continue
        row = _row(e)
        row['skill_total'] += 1
        if first_eval.result == Evaluation.Result.PASS:
            row['skill_pass'] += 1

    return by_restaurant


def _bql_person_totals(employees, month, year):
    """Gop so lieu cohort THEO NHAN SU (tong tu so/mau so tren toan bo pham vi truyen vao,
    KHONG PHAI trung binh cong ty le tung nha hang) - dung cho khoi 'Thong ke theo AM/KCS/OM'."""
    by_restaurant = _bql_cohort_stats(employees, month, year)
    totals = {'on_num': 0, 'on_den': 0, 'skill_pass': 0, 'skill_total': 0}
    for row in by_restaurant.values():
        for key in totals:
            totals[key] += row[key]
    totals['on_rate'] = round(totals['on_num'] / totals['on_den'] * 100) if totals['on_den'] else 0
    totals['skill_rate'] = round(totals['skill_pass'] / totals['skill_total'] * 100) if totals['skill_total'] else 0
    return totals


def _kpi_bql_am_kcs_om_stats(tenant, month, year):
    """Khoi 'Thong ke theo AM/KCS/OM' (Phan 1 muc 7): MOI DONG la 1 nguoi phu trach (tai khoan
    role AM/OM/KCS), so lieu GOP THEO NHAN SU trong pham vi ho quan ly (tong dat/tong dien -
    xem _bql_person_totals), KHONG PHAI trung binh cong ty le tung nha hang.
    AM/OM = toan he thong (BOH+FOH, moi vi tri Khoi Nha hang). KCS = CHI nhan su bep (BOH -
    xem _is_boh_position), gop cac nha hang KCS phu trach (UserRestaurantAssignment, fallback
    User.restaurant - giong logic get_restaurant_scope)."""
    from accounts.models import UserRestaurantAssignment

    all_employees = list(
        Employee.objects.filter(tenant=tenant, is_legacy=False).select_related('restaurant')
    )

    rows = []
    for u in User.objects.filter(tenant=tenant, role__in=('am', 'om')).order_by('username'):
        totals = _bql_person_totals(all_employees, month, year)
        rows.append({
            'role': (u.role or '').upper(), 'name': u.full_name or u.username,
            'scope': 'Toàn hệ thống (BOH + FOH)', 'emp_count': totals['on_den'], **totals,
        })

    for u in User.objects.filter(tenant=tenant, role='kcs').order_by('username'):
        restaurant_ids = set(u.restaurant_assignments.values_list('restaurant_id', flat=True))
        if not restaurant_ids and u.restaurant_id:
            restaurant_ids = {u.restaurant_id}
        kitchen_employees = [
            e for e in all_employees
            if e.restaurant_id in restaurant_ids and _is_boh_position(e.position)
        ]
        totals = _bql_person_totals(kitchen_employees, month, year)
        rows.append({
            'role': 'KCS', 'name': u.full_name or u.username,
            'scope': f'{len(restaurant_ids)} nhà hàng (chỉ bếp)', 'emp_count': totals['on_den'], **totals,
        })

    return rows


def kpi_bql_report_data(user, month, year):
    """So lieu 'Bao cao KPI BQL' theo thang: % NV moi dung lo trinh + % dat kiem tra ky nang
    lan dau, gom theo nha hang (chi Khoi Nha hang) + khoi 'Thong ke theo AM/KCS/OM'. Port
    KpiReportService.gs::trainingKpiData + cap nhat cong thuc theo Apps Script 05-07/08/2026
    (xem _bql_cohort_stats)."""
    by_restaurant = _bql_cohort_stats(scoped_employees(user), month, year)

    rows = []
    totals = {
        'on_num': 0, 'on_den': 0, 'skill_pass': 0, 'skill_total': 0,
        'excl_resigned': 0, 'excl_next_period': 0,
    }
    for row in by_restaurant.values():
        row['on_rate'] = round(row['on_num'] / row['on_den'] * 100) if row['on_den'] else 0
        row['skill_rate'] = round(row['skill_pass'] / row['skill_total'] * 100) if row['skill_total'] else 0
        rows.append(row)
        for key in totals:
            totals[key] += row[key]
    totals['on_rate'] = round(totals['on_num'] / totals['on_den'] * 100) if totals['on_den'] else 0
    totals['skill_rate'] = round(totals['skill_pass'] / totals['skill_total'] * 100) if totals['skill_total'] else 0

    rows.sort(key=lambda r: r['restaurant'])
    return {'rows': rows, 'totals': totals, 'am_kcs': _kpi_bql_am_kcs_om_stats(user.tenant, month, year)}


def get_exported_report_url(tenant, kind, month, year):
    """URL phieu da xuat gan nhat cho (tenant, kind, thang, nam), '' neu chua xuat lan nao -
    dung cho panel 'Phieu ky [M/Y]' hien nut Xem ma khong can xuat lai."""
    report = ExportedReport.objects.filter(tenant=tenant, kind=kind, month=month, year=year).first()
    return report.pdf_url if report else ''


def _save_exported_report(tenant, kind, month, year, pdf_url, user):
    """Luu URL phieu vua xuat cho (tenant, kind, thang, nam). CHI xoa file R2 cu SAU KHI da luu
    ban ghi moi thanh cong, VA chi khi pdf_url moi khac rong (Phan 2.C: "chi xoa SAU KHI luu
    ban moi thanh cong va ban moi co du lieu" - tranh xoa nham phieu tot neu upload/luu loi
    giua chung)."""
    from checklist.storage import delete_by_url

    if not pdf_url:
        return

    old_url = (
        ExportedReport.objects.filter(tenant=tenant, kind=kind, month=month, year=year)
        .values_list('pdf_url', flat=True).first()
    )
    ExportedReport.objects.update_or_create(
        tenant=tenant, kind=kind, month=month, year=year,
        defaults={'pdf_url': pdf_url, 'exported_by': user},
    )
    if old_url and old_url != pdf_url:
        delete_by_url(old_url)


def generate_kpi_report_pdf(user, month, year):
    data = kpi_bql_report_data(user, month, year)
    pdf_bytes = build_kpi_report_pdf({
        'record_no': f'KPIRPT{month}{year}/{user.tenant_id}',
        'tenant_name': user.tenant.name,
        'month': month, 'year': year, 'generated': timezone.now().strftime('%d/%m/%Y'),
        'rows': data['rows'], 'totals': data['totals'], 'am_kcs': data['am_kcs'],
    })
    pdf_url = upload_pdf_bytes(pdf_bytes, f'baocao/{user.tenant_id}/kpi', f'BaoCaoKPI_{year}_{month}')
    _save_exported_report(user.tenant, ExportedReport.Kind.KPI_BQL, month, year, pdf_url, user)
    return pdf_url


def allowance_report_data(user, month, year):
    """Danh sach hoa hong dang Du dieu kien/Da chi (hien tai, khong loc theo thang - giong
    ban goc). month/year chi dung de dat ten phieu/hien thi tieu de. Port
    KpiReportService.gs::allowanceData + them cot ma NV/nha hang trainer (Apps Script
    05-06/08/2026)."""
    qs = commission_queryset_for_user(user).select_related('trainer__restaurant').filter(
        status__in=[Commission.Status.ELIGIBLE, Commission.Status.PAID]
    )
    rows = [
        {
            'trainer': c.trainer.full_name if c.trainer else '',
            'trainer_code': c.trainer.username if c.trainer else '',
            'trainer_restaurant': c.trainer.restaurant.name if c.trainer and c.trainer.restaurant else '',
            'employee': c.employee.name,
            'status': c.get_status_display(),
            'amount': float(c.amount),
        }
        for c in qs
    ]
    total_amount = sum(r['amount'] for r in rows)
    return {'rows': rows, 'total_amount': total_amount}


def generate_allowance_pdf(user, month, year):
    data = allowance_report_data(user, month, year)
    pdf_bytes = build_allowance_pdf({
        'record_no': f'PC{month}{year}/{user.tenant_id}',
        'tenant_name': user.tenant.name,
        'month': month, 'year': year, 'generated': timezone.now().strftime('%d/%m/%Y'),
        'rows': data['rows'], 'total_amount': data['total_amount'],
    })
    pdf_url = upload_pdf_bytes(pdf_bytes, f'baocao/{user.tenant_id}/phucap', f'PhuCapTrainer_{year}_{month}')
    _save_exported_report(user.tenant, ExportedReport.Kind.ALLOWANCE, month, year, pdf_url, user)
    return pdf_url
