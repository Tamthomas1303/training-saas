import re

from django.utils import timezone

from checklist.storage import StorageError, is_data_url, upload_data_url, upload_pdf_bytes
from employees.models import Employee
from employees.permissions import can_evaluate
from employees.services import (
    checklist_progress_percent,
    matching_checklist_items,
    normalize_key,
    random_eval_deadline,
    recompute_final_result,
)

from .models import Evaluation, EvaluationCriteria, EvaluationDetail
from .pdf import build_evaluation_pdf

# Category chua tu khoa nay -> tieu chi (suy tu checklist) mac dinh yeu cau anh minh chung.
# Port EvaluationService.gs fallback: /kỹ năng|thực hành|sơ chế|chế biến/i
REQUIRE_PHOTO_CATEGORY_RE = re.compile(r'kỹ năng|thực hành|sơ chế|chế biến', re.IGNORECASE)

# Vi tri thuoc dien Hoi dong danh gia cap quan ly.
# Port CouncilService.gs::isCouncilPosition: /(quản lý|giám sát|bếp trưởng|bếp phó)/i
COUNCIL_POSITION_RE = re.compile(r'quản lý|giám sát|bếp trưởng|bếp phó', re.IGNORECASE)

COUNCIL_ASPECTS = [
    {'id': 'COUNCIL_TAYNGHE', 'name': 'Tay nghề chuyên môn'},
    {'id': 'COUNCIL_DAOTAO', 'name': 'Kỹ năng đào tạo'},
    {'id': 'COUNCIL_VANHANH', 'name': 'Vận hành ca'},
]

# Ngưỡng đạt đánh giá thực hành = 85% (khớp hệ cũ Config.skillCommission). Phản hồi #7.
SKILL_PASS_THRESHOLD = 85

RANDOM_CHECK_TYPES = ('AM_KCS', 'Training', 'Admin')

# Phân vai: mỗi vai trò chỉ được thực hiện loại đánh giá tương ứng (phản hồi #7 mục 2/D).
# BQL = chỉ đánh giá kỹ năng; AM/KCS = chỉ kiểm tra random; Admin/OM = toàn quyền.
ALLOWED_EVAL_TYPES_BY_ROLE = {
    'bql': {'Skill_BQL'},
    'am': {'AM_KCS'},
    'kcs': {'AM_KCS'},
    'admin': {'Skill_BQL', 'AM_KCS', 'Training', 'Admin'},
    'om': {'Skill_BQL', 'AM_KCS', 'Training', 'Admin'},
}


class ValidationError(Exception):
    pass


def is_council_position(job_position):
    return bool(COUNCIL_POSITION_RE.search(job_position or ''))


def resolve_criteria(employee, eval_type):
    """Tra ve (source, items). Port EvaluationService.gs::getCriteria.

    Khoa loc DB_EvaluationCriteria: brand/position/level_group/eval_type - truong nao de
    trong tren dong tieu chi thi coi la wildcard (khop moi gia tri). Neu khong co dong nao
    khop, fallback: suy tieu chi tu checklist (moi checklist = 1 tieu chi, chia deu 100 diem).
    """
    brand = employee.restaurant.brand if employee.restaurant else ''
    position_key = normalize_key(employee.position)
    level_group = employee.level_group

    # eval_type khac 'Skill_BQL' (AM_KCS/Training/Admin/Council) se dung lai tieu chi gan nhan
    # Skill_BQL neu khong co dong danh rieng cho type do (giong ban goc).
    rows = [
        c for c in EvaluationCriteria.objects.filter(tenant=employee.tenant).order_by('order')
        if (not c.brand or c.brand == brand)
        and (not c.position or normalize_key(c.position) == position_key)
        and (not c.level_group or c.level_group == level_group)
        and (
            not c.eval_type
            or c.eval_type == eval_type
            or (eval_type != 'Skill_BQL' and c.eval_type == 'Skill_BQL')
        )
    ]

    if rows:
        return 'db', [
            {
                'criteria_id': str(c.id),
                'content': c.content,
                'max_score': c.max_score,
                'is_mandatory': c.is_mandatory,
                'require_photo': c.require_photo,
                'section': c.section,
            }
            for c in rows
        ]

    checklist_items = matching_checklist_items(employee)
    n = len(checklist_items) or 1
    per = round(100 / n)
    return 'fallback_checklist', [
        {
            'criteria_id': f'CL:{c.id}',
            'content': c.task_name,
            'max_score': per,
            'is_mandatory': False,
            'require_photo': bool(REQUIRE_PHOTO_CATEGORY_RE.search(c.category or '')),
            'section': c.category,
        }
        for c in checklist_items
    ]


def save_evaluation(user, payload):
    """Luu (nhap hoac hoan thanh) 1 phieu danh gia. Port EvaluationService.gs::saveEvaluation.

    Dung chung boi EvaluationSaveView (API truc tiep) va SyncDraftsView (hang doi offline).
    Nem ValidationError voi thong diep tieng Viet neu khong hop le.
    """
    tenant = user.tenant
    employee_id = payload.get('employee')
    eval_type = payload.get('eval_type')
    if not employee_id or not eval_type:
        raise ValidationError('Thiếu employee hoặc eval_type')

    employee = Employee.objects.filter(pk=employee_id, tenant=tenant).first()
    if not employee:
        raise ValidationError('Không tìm thấy nhân sự')

    if not can_evaluate(user):
        raise ValidationError('Bạn không có quyền đánh giá nhân sự.')

    # D2/D3: chặn loại đánh giá theo vai trò (BQL chỉ kỹ năng; AM/KCS chỉ random).
    role = (user.role or '').lower()
    if eval_type not in ALLOWED_EVAL_TYPES_BY_ROLE.get(role, set()):
        raise ValidationError('Vai trò của bạn không được thực hiện loại đánh giá này.')

    if eval_type == 'Skill_BQL':
        # D3: BQL chỉ đánh giá nhân sự ĐÃ hoàn thành đào tạo tại điểm.
        if checklist_progress_percent(employee) < 100:
            raise ValidationError('Nhân sự chưa hoàn thành đào tạo tại điểm, chưa thể đánh giá kỹ năng.')
        already_done = Evaluation.objects.filter(
            tenant=tenant, employee=employee, eval_type='Skill_BQL', status=Evaluation.Status.DONE,
        ).exists()
        if already_done:
            raise ValidationError('Nhân sự này đã được đánh giá kỹ năng rồi, không thể đánh giá lại.')

    if eval_type in RANDOM_CHECK_TYPES:
        has_bql_pass = Evaluation.objects.filter(
            tenant=tenant, employee=employee, eval_type='Skill_BQL', status=Evaluation.Status.DONE,
        ).exists()
        if not has_bql_pass:
            raise ValidationError('Nhân sự này chưa được BQL đánh giá kỹ năng, chưa thể kiểm tra random.')
        # F: chỉ cho đánh giá random trong 15 ngày kể từ khi hoàn thành đào tạo.
        deadline = random_eval_deadline(employee)
        if deadline and timezone.now().date() > deadline:
            raise ValidationError(
                'Đã quá 15 ngày kể từ khi nhân sự hoàn thành đào tạo — không thể đánh giá random nữa.'
            )

    # Tim ban nhap dang do cua chinh nguoi danh gia nay (khop y upsert cua ban goc:
    # Employee_ID + Evaluator_ID + Eval_Type); neu khong co thi tao moi.
    evaluation = Evaluation.objects.filter(
        tenant=tenant, employee=employee, evaluator=user, eval_type=eval_type,
        status=Evaluation.Status.DRAFT,
    ).first()
    if not evaluation:
        evaluation = Evaluation(tenant=tenant, employee=employee, evaluator=user, eval_type=eval_type)

    # Chu ky
    for field in ('sign_evaluator', 'sign_trainee'):
        value = payload.get(field)
        if not value:
            continue
        if is_data_url(value):
            try:
                url = upload_data_url(value, f'signatures/{tenant.id}', f'{field}_{employee.id}')
            except StorageError as exc:
                raise ValidationError(str(exc)) from exc
            setattr(evaluation, field, url)
        else:
            setattr(evaluation, field, value)

    general_note = payload.get('note')
    if general_note is not None:
        evaluation.note = general_note

    # Tieu chi: lay danh sach chuan tu server (khong tin metadata client gui len) de doi chieu
    # mandatory/require_photo, chi lay diem+anh+ghi chu tu client.
    _, criteria_items = resolve_criteria(employee, eval_type)
    criteria_by_id = {c['criteria_id']: c for c in criteria_items}

    incoming_details = payload.get('details') or []
    incoming_by_id = {str(d.get('criteria_id')): d for d in incoming_details}

    total = 0
    max_total = 0
    mandatory_fail = False
    missing_photo = []
    detail_rows = []

    for criteria_id, meta in criteria_by_id.items():
        incoming = incoming_by_id.get(criteria_id, {})
        score = incoming.get('score', 0) or 0
        try:
            score = max(0, min(float(meta['max_score']), float(score)))
        except (TypeError, ValueError):
            score = 0

        photo_value = incoming.get('photo')
        photo_url = ''
        if photo_value:
            if is_data_url(photo_value):
                try:
                    photo_url = upload_data_url(
                        photo_value, f'evaluation/{tenant.id}/{employee.id}', f'photo_{criteria_id}',
                    )
                except StorageError as exc:
                    raise ValidationError(str(exc)) from exc
            else:
                photo_url = photo_value

        if meta['is_mandatory'] and score <= 0:
            mandatory_fail = True
        if meta['require_photo'] and not photo_url:
            missing_photo.append(meta['content'])

        total += score
        max_total += meta['max_score']
        detail_rows.append(EvaluationDetail(
            tenant=tenant, evaluation=evaluation, criteria_id=criteria_id, content=meta['content'],
            max_score=meta['max_score'], is_mandatory=meta['is_mandatory'], require_photo=meta['require_photo'],
            score=score, photo_url=photo_url, note=incoming.get('note', '') or '',
        ))

    percent = round(total / max_total * 100) if max_total else 0
    want_complete = bool(payload.get('complete'))

    if want_complete:
        if not evaluation.sign_evaluator or not evaluation.sign_trainee:
            raise ValidationError('Cần đủ chữ ký của người đánh giá và nhân viên để hoàn thành.')
        if missing_photo:
            raise ValidationError(
                f'Cần chụp ảnh minh chứng cho {len(missing_photo)} tiêu chí kỹ năng/thực hành trước khi hoàn thành.'
            )

    result = (
        Evaluation.Result.PASS if (percent >= SKILL_PASS_THRESHOLD and not mandatory_fail)
        else Evaluation.Result.FAIL
    )

    evaluation.total_score = total
    evaluation.max_score = max_total
    evaluation.percent = percent
    evaluation.result = result
    evaluation.date = timezone.now().date()
    evaluation.status = Evaluation.Status.DONE if want_complete else Evaluation.Status.DRAFT

    if want_complete:
        evaluation.completed_at = timezone.now()

    evaluation.save()

    EvaluationDetail.objects.filter(evaluation=evaluation).delete()
    for row in detail_rows:
        row.evaluation = evaluation
    EvaluationDetail.objects.bulk_create(detail_rows)

    if want_complete:
        if eval_type in RANDOM_CHECK_TYPES:
            if result == Evaluation.Result.FAIL:
                employee.retrain_deadline = timezone.now().date() + timezone.timedelta(
                    days=employee.probation_days or 15
                )
                employee.commission_status = 'Tạm dừng - đào tạo lại'
                employee.save(update_fields=['retrain_deadline', 'commission_status'])
                # E (phản hồi #7 mục 6): random KHÔNG ĐẠT → reset tiến độ đào tạo về 0 để
                # BQL/trainer đào tạo lại (đưa các mục đã Hoàn thành về Chưa bắt đầu, giữ dữ liệu).
                from checklist.models import TrainingProgress

                TrainingProgress.objects.filter(
                    employee=employee, status=TrainingProgress.Status.DONE,
                ).update(status=TrainingProgress.Status.PENDING, completed_at=None)
                recompute_final_result(employee)
        else:
            employee.skill_score = percent / 100
            employee.skill_result = 'Đạt' if result == Evaluation.Result.PASS else 'Không đạt'
            employee.save(update_fields=['skill_score', 'skill_result'])
            recompute_final_result(employee)

        eval_type_label = dict(Evaluation._meta.get_field('eval_type').choices).get(eval_type, eval_type)
        pdf_bytes = build_evaluation_pdf({
            'record_no': f'{evaluation.id}/{timezone.now().year}',
            'tenant_name': employee.tenant.name,
            'eval_type_label': eval_type_label,
            'date': evaluation.date.strftime('%d/%m/%Y'),
            'employee': {
                'name': employee.name,
                'position': employee.position,
                'restaurant': employee.restaurant.name if employee.restaurant else '',
                'start_date': employee.start_date.strftime('%d/%m/%Y') if employee.start_date else '',
            },
            'evaluator_name': user.full_name or user.username,
            'rows': [
                {'content': d.content, 'max_score': d.max_score, 'score': d.score, 'photo_url': d.photo_url}
                for d in detail_rows
            ],
            'total': total, 'max': max_total, 'percent': percent, 'result': result_label(result),
            'note': evaluation.note,
            'sign_evaluator_url': evaluation.sign_evaluator,
            'sign_trainee_url': evaluation.sign_trainee,
        })
        try:
            pdf_url = upload_pdf_bytes(
                pdf_bytes, f'phieudanhgia/{tenant.id}', f'PhieuDanhGia_{employee.id}_{eval_type}'
            )
        except StorageError as exc:
            raise ValidationError(str(exc)) from exc
        evaluation.pdf_url = pdf_url
        evaluation.save(update_fields=['pdf_url'])

    return evaluation


def result_label(result):
    return 'Đạt' if result == Evaluation.Result.PASS else 'Không đạt'


def save_council_score(user, payload):
    tenant = user.tenant
    employee_id = payload.get('employee')
    employee = Employee.objects.filter(pk=employee_id, tenant=tenant).first()
    if not employee:
        raise ValidationError('Không tìm thấy nhân sự')
    if not can_evaluate(user):
        raise ValidationError('Bạn không có quyền chấm điểm hội đồng.')
    # D3: BQL không tham gia hội đồng — hội đồng do Admin tổ chức (thành viên OM/KCS/AM).
    if (user.role or '').lower() == 'bql':
        raise ValidationError('BQL không tham gia hội đồng đánh giá. Hội đồng do Admin tổ chức (OM/KCS/AM).')
    if not is_council_position(employee.position):
        raise ValidationError('Nhân sự này không thuộc diện đánh giá Hội đồng.')

    scores = payload.get('scores') or {}
    sign = payload.get('sign_evaluator')

    evaluation, _ = Evaluation.objects.get_or_create(
        tenant=tenant, employee=employee, evaluator=user, eval_type='Council',
    )

    if sign:
        if is_data_url(sign):
            try:
                url = upload_data_url(
                    sign, f'signatures/{tenant.id}', f'council_{employee.id}_{user.id}',
                )
            except StorageError as exc:
                raise ValidationError(str(exc)) from exc
            evaluation.sign_evaluator = url
        else:
            evaluation.sign_evaluator = sign

    total = 0
    detail_rows = []
    for aspect in COUNCIL_ASPECTS:
        try:
            score = max(0, min(100, float(scores.get(aspect['id'], 0) or 0)))
        except (TypeError, ValueError):
            score = 0
        total += score
        detail_rows.append(EvaluationDetail(
            tenant=tenant, evaluation=evaluation, criteria_id=aspect['id'], content=aspect['name'],
            max_score=100, score=score,
        ))
    overall = round(total / len(COUNCIL_ASPECTS))

    evaluation.total_score = total
    evaluation.max_score = 100 * len(COUNCIL_ASPECTS)
    evaluation.percent = overall
    evaluation.result = Evaluation.Result.PASS if overall >= SKILL_PASS_THRESHOLD else Evaluation.Result.FAIL
    evaluation.status = Evaluation.Status.DONE
    evaluation.completed_at = timezone.now()
    evaluation.date = timezone.now().date()
    evaluation.save()

    EvaluationDetail.objects.filter(evaluation=evaluation).delete()
    for row in detail_rows:
        row.evaluation = evaluation
    EvaluationDetail.objects.bulk_create(detail_rows)

    return evaluation


def council_summary(employee):
    evals = Evaluation.objects.filter(
        tenant=employee.tenant, employee=employee, eval_type='Council',
    ).select_related('evaluator').prefetch_related('details')

    agg = {a['id']: {'sum': 0, 'n': 0} for a in COUNCIL_ASPECTS}
    judges = []
    for ev in evals:
        details_by_id = {d.criteria_id: float(d.score) for d in ev.details.all()}
        for aspect in COUNCIL_ASPECTS:
            if aspect['id'] in details_by_id:
                agg[aspect['id']]['sum'] += details_by_id[aspect['id']]
                agg[aspect['id']]['n'] += 1
        judges.append({
            'evaluator_id': ev.evaluator_id,
            'name': ev.evaluator.full_name if ev.evaluator else '',
            'role': ev.evaluator.role if ev.evaluator else '',
            'overall': float(ev.percent),
        })

    aspects = [
        {
            'id': a['id'], 'name': a['name'],
            'avg': round(agg[a['id']]['sum'] / agg[a['id']]['n']) if agg[a['id']]['n'] else 0,
            'count': agg[a['id']]['n'],
        }
        for a in COUNCIL_ASPECTS
    ]
    overall = round(sum(a['avg'] for a in aspects) / len(aspects)) if aspects else 0

    return {
        'aspects': aspects,
        'overall': overall,
        'judge_count': len(judges),
        'judges': judges,
        'is_council_position': is_council_position(employee.position),
    }


def finalize_council(employee):
    aggregation = council_summary(employee)
    if aggregation['judge_count'] < 2:
        raise ValidationError('Cần ít nhất 2 giám khảo chấm trước khi chốt hội đồng.')

    by_id = {a['id']: a['avg'] for a in aggregation['aspects']}
    tay_nghe = by_id.get('COUNCIL_TAYNGHE', 0)
    van_hanh = by_id.get('COUNCIL_VANHANH', 0)

    employee.skill_score = tay_nghe / 100
    employee.skill_result = 'Đạt' if tay_nghe >= SKILL_PASS_THRESHOLD else 'Không đạt'
    employee.shift_ops = 'Đạt' if van_hanh >= SKILL_PASS_THRESHOLD else 'Không đạt'
    employee.save(update_fields=['skill_score', 'skill_result', 'shift_ops'])
    recompute_final_result(employee)

    return {
        'tay_nghe': tay_nghe, 'van_hanh': van_hanh,
        'skill_result': employee.skill_result, 'shift_ops': employee.shift_ops,
    }
