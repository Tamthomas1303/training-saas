"""
Logic nghiep vu module Ky thi (MVP Dot 2) - view chi goi ham o day va tra ve, giu view mong
theo dung convention courses/services.py.

Cau truc response_json (dap an nguoi thi nop) THEO TUNG DANG - tu thiet ke (prompt khong quy
dinh wire format), ghi ro o day de FE bam theo:
  single/truefalse : {"option_id": <id QuestionOption>}
  multiple         : {"option_ids": [<id>, ...]}
  text_fill        : {"text": "..."}
  numeric          : {"value": <number>}
  matching         : {"pairs": [{"left": "...", "right": "..."}, ...]}
  dragdrop         : {"placements": {"<gap_id>": "<token>", ...}}
  essay            : {"text": "..."} (khong tu cham, chi luu de nguoi cham tay doc)

Quy tac cham TU DONG (MVP, dung y prompt):
  single/truefalse    : dung 1 option dung -> du diem, sai -> 0.
  multiple/matching/dragdrop : DUNG HOAN TOAN -> du diem, sai bat ky (kem thieu/thua) -> 0.
    TODO (P2/Dot 3): cham diem MOT PHAN cho 3 dang nay - hien tai la all-or-nothing.
  text_fill           : khop 1 trong accepted (theo case_sensitive) -> du diem.
  numeric             : |tra loi - answer| <= tolerance -> du diem.
  essay               : KHONG tu cham, cho cham tay (xem grade_attempt).
"""
import random
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from employees.models import Employee

from .models import Answer, Assessment, AssessmentAssignment, AssessmentQuestion, Attempt, ExamSession, Question


class ValidationError(Exception):
    pass


# ------------------------------------------------------------------ Gan de (giong courses.assign_course)

def assign_assessment(user, assessment, payload, exam_session=None):
    """Gan de thi (bulk tao AssessmentAssignment) theo danh sach employee_ids HOAC bo loc
    position/restaurant_id/group. Bo qua nhan su da duoc gan. Tra ve so nhan su duoc gan MOI.

    exam_session: None (mac dinh, gan tay truc tiep tren De - Dot 2, hanh vi giu NGUYEN) hoac 1
    ExamSession (Dot 4, xem create_exam_session) - stamp vao cac AssessmentAssignment MOI tao de
    gioi han thoi gian mo/dong (xem my_assessments/start_attempt)."""
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
        AssessmentAssignment.objects.filter(assessment=assessment, employee__in=employees)
        .values_list('employee_id', flat=True)
    )
    to_create = [
        AssessmentAssignment(
            tenant=tenant, assessment=assessment, employee=e, assigned_by=user, exam_session=exam_session,
        )
        for e in employees if e.id not in existing_ids
    ]
    AssessmentAssignment.objects.bulk_create(to_create)
    return len(to_create)


# ------------------------------------------------------------------ Ky thi (Dot 4 - ExamSession)

def create_exam_session(user, payload):
    """Tao 1 Ky thi (Prompt_NganHangDe_va_KyThi_kieuCLS.md muc 3): chon 1 De + giao cho ai + dat
    lich -> sinh AssessmentAssignment cho nhan su khop, TAI DUNG assign_assessment (khong viet
    lai). payload: {assessment, title?, start_at?, end_at?} + 1 trong 2: employee_ids HOAC
    position/restaurant_id/group (dung dinh dang voi assign_assessment). Tra ve (session,
    assigned_count)."""
    tenant = user.tenant
    assessment = Assessment.objects.filter(tenant=tenant, pk=payload.get('assessment')).first()
    if not assessment:
        raise ValidationError('Không tìm thấy đề thi.')

    title = (payload.get('title') or '').strip() or assessment.title
    target_config = {
        k: v for k, v in {
            'employee_ids': payload.get('employee_ids'), 'position': payload.get('position'),
            'restaurant_id': payload.get('restaurant_id'), 'group': payload.get('group'),
        }.items() if v
    }

    session = ExamSession.objects.create(
        tenant=tenant, title=title, assessment=assessment,
        start_at=payload.get('start_at') or None, end_at=payload.get('end_at') or None,
        target_config=target_config, created_by=user,
    )
    try:
        assigned_count = assign_assessment(user, assessment, payload, exam_session=session)
    except ValidationError:
        session.delete()
        raise
    return session, assigned_count


def exam_session_tracking(session):
    """Man theo doi 1 Ky thi: tung nhan su duoc giao (qua session nay) - da thi/chua thi, diem,
    dat/khong. Dung Attempt MOI NHAT (attempt_no lon nhat) cua (assessment, employee) do."""
    assignments = (
        AssessmentAssignment.objects.filter(exam_session=session).select_related('employee').order_by('employee__code')
    )
    rows = []
    for a in assignments:
        last = (
            Attempt.objects.filter(assessment=session.assessment, employee=a.employee)
            .order_by('-attempt_no').first()
        )
        rows.append({
            'employee_id': a.employee_id, 'employee_code': a.employee.code, 'employee_name': a.employee.name,
            'done': a.status == AssessmentAssignment.Status.DONE,
            'attempt_status': last.status if last else '',
            'score': last.score if last else None, 'max_score': last.max_score if last else None,
            'percent': last.percent if last else None, 'passed': last.passed if last else None,
        })
    return rows


# ------------------------------------------------------------------ Cham tu dong tung dang

def _normalize_text(value, case_sensitive):
    value = (value or '').strip()
    return value if case_sensitive else value.lower()


def grade_objective_answer(question, response_json, max_points):
    """Tra (auto_score, is_correct) cho 1 cau KHACH QUAN (khong phai essay), theo dung
    max_points truyen vao (co the la points_override cua de, khac question.points goc).
    Tra (None, None) neu la essay (khong tu cham duoc)."""
    response_json = response_json or {}
    max_points = Decimal(max_points)

    if question.type in (Question.Type.SINGLE, Question.Type.TRUEFALSE):
        selected = response_json.get('option_id')
        correct = question.options.filter(is_correct=True).first()
        is_correct = correct is not None and selected is not None and int(selected) == correct.id
        return (max_points if is_correct else Decimal('0'), is_correct)

    if question.type == Question.Type.MULTIPLE:
        try:
            selected = {int(x) for x in (response_json.get('option_ids') or [])}
        except (TypeError, ValueError):
            selected = set()
        correct_ids = set(question.options.filter(is_correct=True).values_list('id', flat=True))
        is_correct = bool(correct_ids) and selected == correct_ids
        return (max_points if is_correct else Decimal('0'), is_correct)

    if question.type == Question.Type.TEXT_FILL:
        config = question.config or {}
        case_sensitive = bool(config.get('case_sensitive'))
        accepted = config.get('accepted') or []
        given = _normalize_text(response_json.get('text'), case_sensitive)
        is_correct = bool(given) and any(given == _normalize_text(a, case_sensitive) for a in accepted)
        return (max_points if is_correct else Decimal('0'), is_correct)

    if question.type == Question.Type.NUMERIC:
        config = question.config or {}
        try:
            value = Decimal(str(response_json.get('value')))
            answer = Decimal(str(config.get('answer')))
            tolerance = Decimal(str(config.get('tolerance', 0)))
        except (InvalidOperation, TypeError, ValueError):
            return (Decimal('0'), False)
        is_correct = abs(value - answer) <= tolerance
        return (max_points if is_correct else Decimal('0'), is_correct)

    if question.type == Question.Type.MATCHING:
        config = question.config or {}
        expected = {(p.get('left'), p.get('right')) for p in (config.get('pairs') or [])}
        given = {(p.get('left'), p.get('right')) for p in (response_json.get('pairs') or [])}
        is_correct = bool(expected) and given == expected
        return (max_points if is_correct else Decimal('0'), is_correct)

    if question.type == Question.Type.DRAGDROP:
        config = question.config or {}
        gaps = config.get('gaps') or []
        placements = response_json.get('placements') or {}
        is_correct = bool(gaps) and all(
            str(placements.get(str(g.get('id')))) == str(g.get('answer')) for g in gaps
        )
        return (max_points if is_correct else Decimal('0'), is_correct)

    return (None, None)  # essay


# ------------------------------------------------------------------ Attempt lifecycle

def _question_points(assessment, question):
    aq = AssessmentQuestion.objects.filter(assessment=assessment, question=question).first()
    if aq and aq.points_override is not None:
        return aq.points_override
    return question.points


def _draw_question_ids(assessment):
    """Danh sach id cau hoi cho 1 attempt MOI - rut ngau nhien theo random_pool_config neu co,
    khong thi dung cau chon tay (AssessmentQuestion), tron neu shuffle_questions."""
    if assessment.random_pool_config:
        cfg = assessment.random_pool_config
        pool = Question.objects.filter(tenant=assessment.tenant, bank_id=cfg.get('bank_id'))
        if cfg.get('difficulty'):
            pool = pool.filter(difficulty=cfg['difficulty'])
        ids = list(pool.values_list('id', flat=True))
        random.shuffle(ids)
        count = cfg.get('count')
        if count:
            ids = ids[:count]
        return ids

    ids = list(
        AssessmentQuestion.objects.filter(assessment=assessment).order_by('order')
        .values_list('question_id', flat=True)
    )
    if assessment.shuffle_questions:
        random.shuffle(ids)
    return ids


def _check_exam_session_window(assignment):
    """Dot 4: neu AssessmentAssignment sinh ra tu 1 ExamSession co lich mo/dong, chan lam bai
    ngoai khoang do. assignment.exam_session=None (gan tay truc tiep, Dot 2) -> KHONG gioi han
    gi (giu nguyen hanh vi cu)."""
    session = assignment.exam_session
    if not session:
        return
    now = timezone.now()
    if session.start_at and now < session.start_at:
        raise ValidationError('Kỳ thi chưa mở.')
    if session.end_at and now > session.end_at:
        raise ValidationError('Kỳ thi đã đóng.')


def start_attempt(employee, assessment):
    if assessment.status != Assessment.Status.PUBLISHED:
        raise ValidationError('Đề thi chưa xuất bản.')
    assignment = (
        AssessmentAssignment.objects.filter(assessment=assessment, employee=employee)
        .select_related('exam_session').first()
    )
    if not assignment:
        raise ValidationError('Bạn chưa được gán đề thi này.')
    _check_exam_session_window(assignment)

    used = Attempt.objects.filter(assessment=assessment, employee=employee).count()
    if used >= assessment.max_attempts:
        raise ValidationError('Bạn đã hết số lần làm bài cho phép.')
    if Attempt.objects.filter(
        assessment=assessment, employee=employee, status=Attempt.Status.IN_PROGRESS,
    ).exists():
        raise ValidationError('Bạn đang có 1 lượt làm bài chưa nộp cho đề này.')

    question_ids = _draw_question_ids(assessment)
    if not question_ids:
        raise ValidationError('Đề thi chưa có câu hỏi.')

    attempt = Attempt.objects.create(
        tenant=employee.tenant, assessment=assessment, employee=employee,
        attempt_no=used + 1, question_ids=question_ids,
    )
    _log_xapi_safe(employee, 'started', 'assessment', assessment.id)
    return attempt


def _log_xapi_safe(employee, verb, object_type, object_id):
    """Dot 3 phan C - log_xapi ban than da tu bat loi, nhung van bao ve them 1 lop o day (import
    tre) de logic lam bai thi (Dot 2) khong bao gio bi anh huong boi Dot 3."""
    try:
        from integration.services import log_xapi

        log_xapi(employee, verb, object_type, object_id)
    except Exception:  # noqa: BLE001
        pass


def _on_exam_finalized_safe(attempt):
    try:
        from integration.services import on_exam_finalized

        on_exam_finalized(attempt)
    except Exception:  # noqa: BLE001 - cham thi (Dot 2) khong duoc phep hong vi Dot 3
        import logging

        logging.getLogger(__name__).exception(
            'on_exam_finalized thất bại cho attempt %s - đã bỏ qua, không chặn luồng chấm thi.',
            attempt.id,
        )


def attempt_question_payload(question, shuffle_options, attempt_seed):
    """Du lieu cau hoi tra ve cho NGUOI THI - KHONG kem dap an dung. Tu tron option/right_items/
    tokens on dinh theo (attempt_seed, question.id) - cung 1 attempt refresh lai van thay dung
    thu tu, khac attempt/nguoi thi khac thi khac thu tu."""
    payload = {
        'id': question.id, 'type': question.type, 'stem_html': question.stem_html,
        'points': question.points, 'media_url': question.media_url,
    }
    rnd = random.Random(f'{attempt_seed}-{question.id}')

    if question.type in (Question.Type.SINGLE, Question.Type.MULTIPLE, Question.Type.TRUEFALSE):
        options = list(question.options.all())
        if shuffle_options:
            rnd.shuffle(options)
        payload['options'] = [
            {'id': o.id, 'content_html': o.content_html, 'media_url': o.media_url} for o in options
        ]
    elif question.type == Question.Type.MATCHING:
        pairs = (question.config or {}).get('pairs') or []
        rights = [p.get('right') for p in pairs]
        rnd.shuffle(rights)
        payload['left_items'] = [p.get('left') for p in pairs]
        payload['right_items'] = rights
    elif question.type == Question.Type.DRAGDROP:
        cfg = question.config or {}
        tokens = list(cfg.get('tokens') or [])
        rnd.shuffle(tokens)
        payload['tokens'] = tokens
        payload['gaps'] = [{'id': g.get('id')} for g in (cfg.get('gaps') or [])]
    # text_fill/numeric/essay: khong can them gi, chi o nhap.
    return payload


def attempt_questions_payload(attempt):
    questions = {
        q.id: q for q in Question.objects.filter(id__in=attempt.question_ids).prefetch_related('options')
    }
    return [
        attempt_question_payload(questions[qid], attempt.assessment.shuffle_options, attempt.id)
        for qid in attempt.question_ids if qid in questions
    ]


def attempt_detail_payload(attempt):
    """Chi tiet 1 lan lam bai DANG LAM - dung cho ca 'bat dau' va 'tiep tuc lam bai' (FE goi
    lai endpoint nay sau khi start de lay cau hoi + dap an da luu tam, tranh trung logic)."""
    saved = {a.question_id: a.response_json for a in attempt.answers.all()}
    return {
        'attempt_id': attempt.id, 'time_limit_min': attempt.assessment.time_limit_min,
        'started_at': attempt.started_at, 'questions': attempt_questions_payload(attempt),
        'answers': saved,
    }


def save_answers(attempt, items):
    """items: [{question, response}, ...] (chap nhan ca 1 dict don le - view chuan hoa truoc)."""
    if attempt.status != Attempt.Status.IN_PROGRESS:
        raise ValidationError('Bài thi đã nộp, không thể sửa câu trả lời.')
    saved = []
    for item in items:
        qid = item.get('question')
        if qid not in attempt.question_ids:
            continue
        answer, _ = Answer.objects.update_or_create(
            tenant=attempt.tenant, attempt=attempt, question_id=qid,
            defaults={'response_json': item.get('response') or {}},
        )
        saved.append(answer)
    return saved


def submit_attempt(attempt):
    if attempt.status != Attempt.Status.IN_PROGRESS:
        raise ValidationError('Bài thi đã nộp trước đó.')

    questions = {q.id: q for q in Question.objects.filter(id__in=attempt.question_ids)}
    total_score = Decimal('0')
    max_score = Decimal('0')
    has_essay = False

    for qid in attempt.question_ids:
        question = questions.get(qid)
        if not question:
            continue
        points = Decimal(_question_points(attempt.assessment, question))
        max_score += points
        answer, _ = Answer.objects.get_or_create(tenant=attempt.tenant, attempt=attempt, question=question)
        if question.type == Question.Type.ESSAY:
            has_essay = True
            continue
        auto_score, is_correct = grade_objective_answer(question, answer.response_json, points)
        answer.auto_score = auto_score
        answer.is_correct = is_correct
        answer.save(update_fields=['auto_score', 'is_correct'])
        total_score += auto_score

    attempt.submitted_at = timezone.now()
    attempt.max_score = max_score
    attempt.score = total_score
    if has_essay:
        attempt.status = Attempt.Status.SUBMITTED
        attempt.percent = None
        attempt.passed = None
    else:
        attempt.percent = round(total_score / max_score * 100, 2) if max_score else Decimal('0')
        attempt.passed = attempt.percent >= attempt.assessment.pass_mark
        attempt.status = Attempt.Status.GRADED
    attempt.save()

    AssessmentAssignment.objects.filter(
        assessment=attempt.assessment, employee=attempt.employee,
    ).update(status=AssessmentAssignment.Status.DONE)

    # Dot 3 phan A/C/D: chi ban hanh khi KHONG co essay - da GRADED (final) ngay luc nop. Neu co
    # essay, cho grade_attempt ban hanh (moc "final" thuc su la luc do, khong phai luc nop).
    if not has_essay:
        _on_exam_finalized_safe(attempt)
    return attempt


def grade_attempt(attempt, grader, scores):
    """scores: {question_id: manual_score} - chi ap dung cho cau essay. Cong don vao score da
    co (cac cau khach quan da tu cham luc submit), tinh lai percent/passed, chuyen GRADED."""
    if attempt.status != Attempt.Status.SUBMITTED:
        raise ValidationError('Bài thi không ở trạng thái chờ chấm.')

    objective_score = sum(
        (a.auto_score or Decimal('0'))
        for a in attempt.answers.exclude(question__type=Question.Type.ESSAY)
    )
    essay_score = Decimal('0')
    for qid_raw, value in (scores or {}).items():
        try:
            qid = int(qid_raw)
            manual_score = Decimal(str(value))
        except (TypeError, ValueError):
            continue
        answer = attempt.answers.filter(question_id=qid, question__type=Question.Type.ESSAY).first()
        if not answer:
            continue
        answer.manual_score = manual_score
        answer.graded_by = grader
        answer.save(update_fields=['manual_score', 'graded_by'])
        essay_score += manual_score

    attempt.score = objective_score + essay_score
    attempt.percent = round(attempt.score / attempt.max_score * 100, 2) if attempt.max_score else Decimal('0')
    attempt.passed = attempt.percent >= attempt.assessment.pass_mark
    attempt.status = Attempt.Status.GRADED
    attempt.save()
    _on_exam_finalized_safe(attempt)
    return attempt


def attempt_result_payload(attempt):
    """Ket qua tra ve cho NGUOI THI, tuan theo Assessment.show_result_mode:
    - immediately: diem + chi tiet dung/sai + giai thich tung cau.
    - after_close: CHI hien chi tiet khi de da chuyen sang 'archived' (khong co field 'ngay
      dong' rieng trong model - suy luan dung Assessment.status lam moc 'dong de', vi day la
      trang thai 'dong' duy nhat co san). Truoc do chi hien diem tong (nhu score_only).
    - score_only: chi diem, khong hien dung/sai/giai thich.

    Dot 4 (tab Tuy chinh kieu CLS) them 2 lop GIOI HAN THEM (khong thay the logic tren, chi
    thu hep lai neu duoc cau hinh chat hon):
    - show_score=False -> an het diem/%(passed van giu, la 'dat/khong dat' chu khong phai diem).
    - review_mode='none'|'score_only' -> ep show_detail=False du show_result_mode co cho phep,
      dung mac dinh 'full_detail' thi khong doi gi (giu nguyen hanh vi de tao truoc Dot 4)."""
    assessment = attempt.assessment
    base = {
        'attempt_id': attempt.id, 'status': attempt.status,
        'score': attempt.score if assessment.show_score else None,
        'max_score': attempt.max_score if assessment.show_score else None,
        'percent': attempt.percent if assessment.show_score else None,
        'passed': attempt.passed,
    }
    mode = assessment.show_result_mode
    show_detail = mode == Assessment.ShowResultMode.IMMEDIATELY or (
        mode == Assessment.ShowResultMode.AFTER_CLOSE
        and assessment.status == Assessment.Status.ARCHIVED
    )
    if assessment.review_mode in (Assessment.ReviewMode.NONE, Assessment.ReviewMode.SCORE_ONLY):
        show_detail = False
    if not show_detail:
        return base

    base['details'] = [
        {
            'question_id': a.question_id, 'is_correct': a.is_correct,
            'auto_score': a.auto_score, 'manual_score': a.manual_score,
            'explanation_html': a.question.explanation_html,
        }
        for a in attempt.answers.select_related('question')
    ]
    return base


def reorder_assessment_questions(tenant, items):
    """Cap nhat 'order' hang loat cho AssessmentQuestion. items: [{id, order}, ...] - giong het
    courses.services.reorder_items, viet rieng vi khong muon exams phu thuoc nguoc vao courses."""
    ids = [item['id'] for item in items]
    by_id = {obj.id: obj for obj in AssessmentQuestion.objects.filter(tenant=tenant, id__in=ids)}
    updated = []
    for item in items:
        obj = by_id.get(item['id'])
        if obj is None:
            continue
        obj.order = item['order']
        updated.append(obj)
    AssessmentQuestion.objects.bulk_update(updated, ['order'])
    return len(updated)


def my_assessments(employee):
    """Dot 4: neu assignment sinh tu 1 ExamSession co lich, CHI hien trong khoang [start_at,
    end_at] cua ky thi do (dung y prompt 'nguoi thi thay ky thi trong Bai thi cua toi TRONG
    KHOANG THOI GIAN MO'). Assignment gan tay truc tiep (exam_session=None, Dot 2) luon hien -
    hanh vi giu NGUYEN."""
    now = timezone.now()
    assignments = AssessmentAssignment.objects.filter(employee=employee).select_related('assessment', 'exam_session')
    result = []
    for a in assignments:
        session = a.exam_session
        if session:
            if session.start_at and now < session.start_at:
                continue
            if session.end_at and now > session.end_at:
                continue
        attempts = list(
            Attempt.objects.filter(assessment=a.assessment, employee=employee).order_by('-attempt_no')
        )
        last = attempts[0] if attempts else None
        result.append({
            'assignment_id': a.id, 'assessment_id': a.assessment_id, 'title': a.assessment.title,
            'time_limit_min': a.assessment.time_limit_min, 'due_date': a.due_date,
            'exam_session_end_at': session.end_at if session else None,
            'attempts_used': len(attempts), 'max_attempts': a.assessment.max_attempts,
            'in_progress_attempt_id': next(
                (att.id for att in attempts if att.status == Attempt.Status.IN_PROGRESS), None,
            ),
            'last_result': attempt_result_payload(last) if last else None,
        })
    return result
