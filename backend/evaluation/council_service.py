"""
council_service.py — nghiệp vụ Hội đồng đánh giá cấp O (mục 7 / Phase 2).

3 loại đánh giá:
  - Vận hành ca (ShiftOps): cá nhân AM (FOH) / KCS (BOH) chấm; tiêu chí Đạt/Không; ≥80% đạt.
  - Tay nghề (Council_Skill): hội đồng, mỗi giám khảo chấm THEO MÓN (1 bản/món), thang 1–4;
    kết quả giám khảo = TB các món; hội đồng = TB các giám khảo; ≥80% đạt.
  - Phỏng vấn (Council_Interview): hội đồng, mỗi người theo VAI (HCNS/DaoTao/VanHanh/QC) một bộ
    tiêu chí, thang 1–4; hội đồng = TB các người phỏng vấn; ≥80% đạt.
Người ngoài (QC/HCNS...) chấm qua link khách mời (token), không cần tài khoản.
"""
import secrets

from django.utils import timezone

from checklist.storage import StorageError, is_data_url, upload_data_url
from employees.models import Employee
from employees.services import normalize_key, recompute_final_result

from .models import Council, CouncilMember, Evaluation, EvaluationCriteria, EvaluationDetail

PASS_THRESHOLD = 80
COUNCIL_ADMIN_ROLES = {'admin', 'om'}  # Phòng Đào tạo = admin trong hệ thống này


class CouncilError(Exception):
    pass


def position_group(employee):
    """FOH (Quản lý/Giám sát) hay BOH (Bếp trưởng/phó) theo vị trí."""
    return 'BOH' if 'bep' in normalize_key(employee.position) else 'FOH'


def is_council_position(employee):
    p = normalize_key(employee.position)
    return any(k in p for k in ('quan ly', 'giam sat', 'bep truong', 'bep pho'))


def _criteria(tenant, eval_type, group, dept_role=''):
    qs = EvaluationCriteria.objects.filter(tenant=tenant, eval_type=eval_type, position_group=group)
    if dept_role:
        qs = qs.filter(dept_role=dept_role)
    return list(qs.order_by('order'))


def _criteria_payload(rows):
    return [
        {'criteria_id': str(c.id), 'content': c.content, 'section': c.section,
         'max_score': c.max_score, 'dept_role': c.dept_role}
        for c in rows
    ]


def _upload_sign(tenant, sign, tag):
    if sign and is_data_url(sign):
        try:
            return upload_data_url(sign, f'signatures/{tenant.id}', tag)
        except StorageError as exc:
            raise CouncilError(str(exc)) from exc
    return sign or ''


def _score_evaluation(ev, tenant, criteria_rows, scores):
    """Ghi điểm cho 1 phiếu: cập nhật details + tính percent + result. Trả percent."""
    total = 0.0
    maxt = 0.0
    detail_rows = []
    for c in criteria_rows:
        cid = str(c.id)
        try:
            sc = float(scores.get(cid, 0) or 0)
        except (TypeError, ValueError):
            sc = 0.0
        sc = max(0.0, min(float(c.max_score), sc))
        total += sc
        maxt += float(c.max_score)
        detail_rows.append(EvaluationDetail(
            tenant=tenant, evaluation=ev, criteria_id=cid, content=c.content,
            max_score=c.max_score, score=sc,
        ))
    percent = round(total / maxt * 100) if maxt else 0
    ev.total_score = total
    ev.max_score = maxt
    ev.percent = percent
    ev.result = Evaluation.Result.PASS if percent >= PASS_THRESHOLD else Evaluation.Result.FAIL
    ev.status = Evaluation.Status.DONE
    ev.date = timezone.now().date()
    ev.completed_at = timezone.now()
    ev.save()
    EvaluationDetail.objects.filter(evaluation=ev).delete()
    for r in detail_rows:
        r.evaluation = ev
    EvaluationDetail.objects.bulk_create(detail_rows)
    return percent


# ---------------- Vận hành ca (AM/KCS) ----------------
def shiftops_form(employee):
    return {
        'position_group': position_group(employee),
        'criteria': _criteria_payload(_criteria(employee.tenant, 'ShiftOps', position_group(employee))),
    }


def submit_shiftops(user, employee, scores, sign=''):
    role = (user.role or '').lower()
    grp = position_group(employee)
    if grp == 'FOH' and role not in ('am', 'admin', 'om'):
        raise CouncilError('Vận hành ca (FOH) do AM chấm.')
    if grp == 'BOH' and role not in ('kcs', 'admin', 'om'):
        raise CouncilError('Vận hành ca (BOH) do KCS chấm.')
    rows = _criteria(employee.tenant, 'ShiftOps', grp)
    if not rows:
        raise CouncilError('Chưa có bộ tiêu chí vận hành ca cho nhóm này.')

    ev = (Evaluation.objects.filter(tenant=employee.tenant, employee=employee, eval_type='ShiftOps',
                                    evaluator=user).first()
          or Evaluation(tenant=employee.tenant, employee=employee, eval_type='ShiftOps', evaluator=user))
    ev.sign_evaluator = _upload_sign(employee.tenant, sign, f'shiftops_{employee.id}_{user.id}')
    percent = _score_evaluation(ev, employee.tenant, rows, scores)
    employee.shift_ops = 'Đạt' if percent >= PASS_THRESHOLD else 'Không đạt'
    employee.save(update_fields=['shift_ops'])
    recompute_final_result(employee)
    return {'percent': percent, 'result': employee.shift_ops}


# ---------------- Lập hội đồng + thành viên ----------------
def create_council(user, employee, kind):
    if (user.role or '').lower() not in COUNCIL_ADMIN_ROLES:
        raise CouncilError('Chỉ Admin/Phòng Đào tạo được lập hội đồng.')
    if not is_council_position(employee):
        raise CouncilError('Chỉ áp dụng cho nhân sự cấp O (Quản lý/Giám sát/Bếp trưởng/Bếp phó).')
    if kind not in (Council.Kind.SKILL, Council.Kind.INTERVIEW):
        raise CouncilError('Loại hội đồng không hợp lệ.')
    council = Council.objects.filter(
        tenant=employee.tenant, employee=employee, kind=kind, status=Council.Status.OPEN,
    ).first()
    if not council:
        council = Council.objects.create(
            tenant=employee.tenant, employee=employee, kind=kind, created_by=user,
        )
    return council


def add_member(user, council, user_id=None, guest_name='', guest_dept='', dept_role=''):
    if (user.role or '').lower() not in COUNCIL_ADMIN_ROLES:
        raise CouncilError('Chỉ Admin/Phòng Đào tạo được thêm thành viên.')
    member = CouncilMember(tenant=council.tenant, council=council, dept_role=dept_role)
    if user_id:
        from accounts.models import User

        u = User.objects.filter(pk=user_id, tenant=council.tenant).first()
        if not u:
            raise CouncilError('Không tìm thấy tài khoản thành viên.')
        member.user = u
    else:
        if not guest_name:
            raise CouncilError('Cần tên người đánh giá khách mời.')
        member.guest_name = guest_name
        member.guest_dept = guest_dept
        member.token = secrets.token_urlsafe(24)
    member.save()
    return member


def member_form(member):
    """Bộ tiêu chí + phiếu hiện có của 1 thành viên (giám khảo/khách mời)."""
    council = member.council
    employee = council.employee
    grp = position_group(employee)
    if council.kind == Council.Kind.SKILL:
        rows = _criteria(employee.tenant, 'Council_Skill', grp)
        eval_type = 'Council_Skill'
    else:
        rows = _criteria(employee.tenant, 'Council_Interview', grp, dept_role=member.dept_role)
        eval_type = 'Council_Interview'
    existing = list(Evaluation.objects.filter(council=council, council_member=member, eval_type=eval_type)
                    .prefetch_related('details'))
    return {
        'council_kind': council.kind,
        'employee': {'name': employee.name, 'position': employee.position,
                     'restaurant': employee.restaurant.name if employee.restaurant else ''},
        'dept_role': member.dept_role,
        'criteria': _criteria_payload(rows),
        'submissions': [
            {'id': e.id, 'dish_name': e.dish_name, 'percent': float(e.percent), 'result': e.result,
             'scores': {d.criteria_id: float(d.score) for d in e.details.all()}}
            for e in existing
        ],
    }


def submit_member_score(member, scores, dish_name='', sign='', evaluator_user=None):
    """1 thành viên chấm: tay nghề = 1 bản/món (dish_name); phỏng vấn = 1 bản theo vai."""
    council = member.council
    employee = council.employee
    grp = position_group(employee)
    if council.kind == Council.Kind.SKILL:
        eval_type = 'Council_Skill'
        rows = _criteria(employee.tenant, 'Council_Skill', grp)
        if not dish_name:
            raise CouncilError('Cần nhập tên món cho bản chấm tay nghề.')
    else:
        eval_type = 'Council_Interview'
        rows = _criteria(employee.tenant, 'Council_Interview', grp, dept_role=member.dept_role)
        dish_name = ''
    if not rows:
        raise CouncilError('Chưa có bộ tiêu chí phù hợp.')

    lookup = dict(tenant=employee.tenant, employee=employee, eval_type=eval_type,
                  council=council, council_member=member, dish_name=dish_name)
    ev = Evaluation.objects.filter(**lookup).first() or Evaluation(**lookup)
    ev.evaluator = evaluator_user  # None nếu khách mời
    ev.sign_evaluator = _upload_sign(employee.tenant, sign, f'council_{council.id}_{member.id}')
    percent = _score_evaluation(ev, employee.tenant, rows, scores)
    member.submitted = True
    member.save(update_fields=['submitted'])
    return {'percent': percent, 'result': ev.result, 'dish_name': dish_name}


# ---------------- Tổng hợp + chốt ----------------
def council_detail(council):
    employee = council.employee
    eval_type = 'Council_Skill' if council.kind == Council.Kind.SKILL else 'Council_Interview'
    members = list(council.members.select_related('user'))
    evals = list(Evaluation.objects.filter(council=council, eval_type=eval_type, status='done'))
    by_member = {}
    for e in evals:
        by_member.setdefault(e.council_member_id, []).append(e)

    member_rows = []
    member_results = []
    for m in members:
        evs = by_member.get(m.id, [])
        if council.kind == Council.Kind.SKILL:
            # kết quả giám khảo = TB các món
            avg = round(sum(float(e.percent) for e in evs) / len(evs)) if evs else None
            dishes = [{'dish_name': e.dish_name, 'percent': float(e.percent)} for e in evs]
        else:
            avg = round(float(evs[0].percent)) if evs else None
            dishes = []
        if avg is not None:
            member_results.append(avg)
        member_rows.append({
            'member_id': m.id,
            'name': (m.user.full_name or m.user.username) if m.user else m.guest_name,
            'is_guest': m.user_id is None,
            'dept_role': m.dept_role,
            'guest_link': f'/council-guest/{m.token}' if m.token else '',
            'submitted': avg is not None,
            'result_percent': avg,
            'dishes': dishes,
        })

    overall = round(sum(member_results) / len(member_results)) if member_results else 0
    return {
        'council_id': council.id,
        'kind': council.kind,
        'status': council.status,
        'employee': {'id': employee.id, 'name': employee.name, 'position': employee.position},
        'members': member_rows,
        'submitted_count': len(member_results),
        'overall': overall,
        'threshold': PASS_THRESHOLD,
        'passed': overall >= PASS_THRESHOLD,
    }


def finalize_council(user, council):
    if (user.role or '').lower() not in COUNCIL_ADMIN_ROLES:
        raise CouncilError('Chỉ Admin/Phòng Đào tạo được chốt hội đồng.')
    detail = council_detail(council)
    if detail['submitted_count'] < 2:
        raise CouncilError('Cần ít nhất 2 người chấm trước khi chốt hội đồng.')

    employee = council.employee
    overall = detail['overall']
    passed = overall >= PASS_THRESHOLD
    if council.kind == Council.Kind.SKILL:
        employee.skill_score = overall / 100
        employee.skill_result = 'Đạt' if passed else 'Không đạt'
        employee.save(update_fields=['skill_score', 'skill_result'])
    else:
        employee.interview_score = overall / 100
        employee.interview_result = 'Đạt' if passed else 'Không đạt'
        employee.save(update_fields=['interview_score', 'interview_result'])
    council.status = Council.Status.FINALIZED
    council.save(update_fields=['status'])
    recompute_final_result(employee)
    return {'overall': overall, 'passed': passed, 'kind': council.kind}
