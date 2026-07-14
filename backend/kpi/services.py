import datetime
from collections import defaultdict

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date

from checklist.storage import StorageError, is_data_url, upload_data_url, upload_pdf_bytes
from employees.dashboard import _completion_date, _is_pass, scoped_employees
from employees.models import Employee
from employees.permissions import can_access_restaurant, get_restaurant_scope
from employees.services import probation_conditions, trainer_of
from restaurants.models import Restaurant

from .models import Commission, KpiParticipant, KpiSession
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

    commission.trainer = trainer_of(employee)
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


def kpi_bql_report_data(user, month, year):
    """So lieu 'Bao cao KPI BQL' theo thang: % NV moi dung lo trinh + % dat kiem tra ky nang
    lan dau, gom theo nha hang. Port KpiReportService.gs::trainingKpiData."""
    from evaluation.models import Evaluation

    by_restaurant = {}

    for e in scoped_employees(user):
        if not e.start_date:
            continue
        tier = _kpi_tier_days(e.position)
        deadline = e.start_date + datetime.timedelta(days=tier)
        if not (deadline.month == month and deadline.year == year):
            continue
        rid = e.restaurant_id or 0
        row = by_restaurant.setdefault(rid, {
            'restaurant': e.restaurant.name if e.restaurant else 'Khác',
            'brand': e.restaurant.brand if e.restaurant else '',
            'on_num': 0, 'on_den': 0, 'skill_pass': 0, 'skill_total': 0,
        })
        row['on_den'] += 1
        completed = _completion_date(e)
        on_track = _is_pass(e) and completed and (completed - e.start_date).days <= tier
        if on_track:
            row['on_num'] += 1

    scope = get_restaurant_scope(user)
    skill_evals = Evaluation.objects.filter(
        tenant=user.tenant, eval_type='Skill_BQL', status='done', date__month=month, date__year=year,
    ).select_related('employee', 'employee__restaurant')
    if not scope['all']:
        skill_evals = skill_evals.filter(employee__restaurant_id__in=scope['restaurant_ids'])

    for ev in skill_evals:
        e = ev.employee
        rid = e.restaurant_id or 0
        row = by_restaurant.setdefault(rid, {
            'restaurant': e.restaurant.name if e.restaurant else 'Khác',
            'brand': e.restaurant.brand if e.restaurant else '',
            'on_num': 0, 'on_den': 0, 'skill_pass': 0, 'skill_total': 0,
        })
        row['skill_total'] += 1
        if ev.result == Evaluation.Result.PASS:
            row['skill_pass'] += 1

    rows = []
    totals = {'on_num': 0, 'on_den': 0, 'skill_pass': 0, 'skill_total': 0}
    for row in by_restaurant.values():
        row['on_rate'] = round(row['on_num'] / row['on_den'] * 100) if row['on_den'] else 0
        row['skill_rate'] = round(row['skill_pass'] / row['skill_total'] * 100) if row['skill_total'] else 0
        rows.append(row)
        for key in ('on_num', 'on_den', 'skill_pass', 'skill_total'):
            totals[key] += row[key]
    totals['on_rate'] = round(totals['on_num'] / totals['on_den'] * 100) if totals['on_den'] else 0
    totals['skill_rate'] = round(totals['skill_pass'] / totals['skill_total'] * 100) if totals['skill_total'] else 0

    rows.sort(key=lambda r: r['restaurant'])
    return {'rows': rows, 'totals': totals}


def generate_kpi_report_pdf(user, month, year):
    data = kpi_bql_report_data(user, month, year)
    pdf_bytes = build_kpi_report_pdf({
        'record_no': f'KPIRPT{month}{year}/{user.tenant_id}',
        'tenant_name': user.tenant.name,
        'month': month, 'year': year,
        'rows': data['rows'], 'totals': data['totals'],
    })
    return upload_pdf_bytes(pdf_bytes, f'baocao/{user.tenant_id}/kpi', f'BaoCaoKPI_{year}_{month}')


def allowance_report_data(user, month, year):
    """Danh sach hoa hong dang Du dieu kien/Da chi (hien tai, khong loc theo thang - giong
    ban goc). month/year chi dung de dat ten phieu/hien thi tieu de. Port
    KpiReportService.gs::allowanceData."""
    qs = commission_queryset_for_user(user).filter(
        status__in=[Commission.Status.ELIGIBLE, Commission.Status.PAID]
    )
    rows = [
        {
            'trainer': c.trainer.full_name if c.trainer else '',
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
        'month': month, 'year': year,
        'rows': data['rows'], 'total_amount': data['total_amount'],
    })
    return upload_pdf_bytes(pdf_bytes, f'baocao/{user.tenant_id}/phucap', f'PhuCapTrainer_{year}_{month}')
