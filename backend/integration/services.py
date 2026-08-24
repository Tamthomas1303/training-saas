"""
Logic "noi he thong" - Dot 3/3. 4 phan:
  A. sync_result_to_profile(...)   - dong bo CourseResult/ExamResult + goi lai recompute co san.
  B. (xem courses.services.confirm_offline_completion - dung OfflineConfirmation model o day)
  C. log_xapi(...)                 - ghi XapiStatement, khong bao gio chan luong chinh.
  D. issue_certificate(...), check_and_issue_programs(...) - nen chung chi.

AN TOAN (bat buoc doc truoc khi sua): sync_result_to_profile KHONG duoc tu tinh pass thu viec -
chi ghi CourseResult/ExamResult (nguon 'internal_lms') roi GOI LAI
employees.services.recompute_final_result (ham co san, KHONG sua). KHONG BAO GIO ghi de 1 dong
da co nguon 'cls' (du dong do dang o trang thai gi) - xem _sync_course/_sync_exam.

Import courses.models/exams.models CHI trong than ham (deferred) de tranh vong lap: courses/
exams goi services o day; o day khong duoc import courses.services/exams.services (chi models).
"""
import logging
import uuid

from django.utils import timezone

from checklist.storage import upload_pdf_bytes

from .pdf import build_certificate_pdf

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    pass


# ==================================================================== Phan A: dong bo ho so

def sync_result_to_profile(target):
    """Diem noi DUY NHAT tu courses/exams khi hoan thanh khoa (courses.Enrollment) hoac thi dat
    (exams.Attempt). Dispatch theo kieu doi tuong truyen vao."""
    from courses.models import Enrollment
    from exams.models import Attempt

    if isinstance(target, Enrollment):
        return _sync_course(target)
    if isinstance(target, Attempt):
        return _sync_exam(target)
    raise IntegrationError(f'Không hỗ trợ đồng bộ cho {type(target)!r}')


def _sync_course(enrollment):
    from cls_sync.models import CourseResult, ResultSource
    from employees.services import recompute_final_result

    course = enrollment.course
    course_name = (course.sync_course_code or '').strip()
    if not course_name:
        logger.warning(
            'sync_result_to_profile: khoa "%s" (id=%s) chưa gán sync_course_code - bỏ qua đồng bộ.',
            course.title, course.id,
        )
        return None

    existing = CourseResult.objects.filter(employee=enrollment.employee, course_name=course_name).first()
    if existing and existing.source == ResultSource.CLS:
        logger.info(
            'sync_result_to_profile: đã có CourseResult nguồn CLS cho nhân sự %s / khóa "%s" - KHÔNG động vào.',
            enrollment.employee_id, course_name,
        )
        return existing

    result, _created = CourseResult.objects.update_or_create(
        tenant=enrollment.tenant, employee=enrollment.employee, course_name=course_name,
        defaults={'status': 'Đạt', 'source': ResultSource.INTERNAL_LMS},
    )
    recompute_final_result(enrollment.employee)
    return result


def _sync_exam(attempt):
    from cls_sync.models import ExamResult, ResultSource
    from employees.services import recompute_final_result

    assessment = attempt.assessment
    exam_name = (assessment.sync_exam_type or '').strip()
    if not exam_name:
        logger.warning(
            'sync_result_to_profile: đề thi "%s" (id=%s) chưa gán sync_exam_type - bỏ qua đồng bộ.',
            assessment.title, assessment.id,
        )
        return None

    existing = ExamResult.objects.filter(
        employee=attempt.employee, exam_name=exam_name, attempt=attempt.attempt_no,
    ).first()
    if existing and existing.source == ResultSource.CLS:
        logger.info(
            'sync_result_to_profile: đã có ExamResult nguồn CLS cho nhân sự %s / "%s" lần %s - KHÔNG động vào.',
            attempt.employee_id, exam_name, attempt.attempt_no,
        )
        return existing

    result, _created = ExamResult.objects.update_or_create(
        tenant=attempt.tenant, employee=attempt.employee, exam_name=exam_name, attempt=attempt.attempt_no,
        defaults={'score': attempt.percent, 'passed': bool(attempt.passed), 'source': ResultSource.INTERNAL_LMS},
    )
    recompute_final_result(attempt.employee)
    return result


# ==================================================================== Phan C: log xAPI

def log_xapi(employee, verb, object_type, object_id, result_json=None, context_json=None):
    """Ghi 1 dong XapiStatement. KHONG BAO GIO duoc lam hong luong chinh neu loi (vd tenant/
    employee null trong test) - chi log canh bao va bo qua."""
    from .models import XapiStatement

    try:
        XapiStatement.objects.create(
            tenant=employee.tenant, employee=employee, verb=verb, object_type=object_type,
            object_id=object_id, result_json=result_json, context_json=context_json,
        )
    except Exception:  # noqa: BLE001 - log xAPI khong bao gio duoc chan nghiep vu chinh
        logger.exception('log_xapi thất bại (verb=%s, object=%s:%s) - bỏ qua.', verb, object_type, object_id)


# ==================================================================== Phan D: nen chung chi

def program_eligible(employee, program):
    """Tra (eligible: bool, detail: dict) theo rule_config.kind - xem CertProgram docstring."""
    cfg = program.rule_config or {}
    kind = cfg.get('kind')

    if kind == 'positions_count':
        from accounts.services import get_grading_config
        from employees.career import positions_achieved_count

        count = positions_achieved_count(employee)
        required = cfg.get('count', get_grading_config(employee.tenant).cert_positions_required)
        return count >= required, {'positions_count': count}

    if kind == 'course_exam':
        from django.db.models.functions import Coalesce

        from accounts.services import get_grading_config
        from cls_sync.models import CourseResult, ExamResult

        course_ok = not cfg.get('course') or CourseResult.objects.filter(
            employee=employee, course_name=cfg['course'], status='Đạt',
        ).exists()
        exam_ok = not cfg.get('exam') or (
            ExamResult.objects.filter(employee=employee, exam_name=cfg['exam'])
            .annotate(computed_score=Coalesce('score_adjusted', 'score'))
            .filter(computed_score__gte=get_grading_config(employee.tenant).exam_pass_percent)
            .exists()
        )
        return (course_ok and exam_ok), {'course_ok': course_ok, 'exam_ok': exam_ok}

    if kind == 'bql_position':
        from employees.services import checklist_progress_percent, exam_pass

        require = cfg.get('require') or []
        details = {}
        if 'training' in require:
            details['training'] = checklist_progress_percent(employee) >= 100
        if 'final_exam' in require:
            details['final_exam'] = exam_pass(employee)
        # council/shift_eval/interview: cho tich hop module evaluation (P2) - danh dau 'pending',
        # KHONG chan cap chung chi MVP vi chua co du lieu de kiem (dung y prompt).
        for pending_key in ('council', 'shift_eval', 'interview'):
            if pending_key in require:
                details[pending_key] = 'pending'
        checked = [v for v in details.values() if isinstance(v, bool)]
        return (bool(checked) and all(checked)), details

    return False, {'error': f'rule_config.kind không hợp lệ: {kind!r}'}


def _generate_cert_code():
    return f'CC{timezone.now():%Y%m}{uuid.uuid4().hex[:8].upper()}'


def issue_certificate(employee, template, ref_type, ref_id, program=None,
                       program_or_course_name='', completion_line=''):
    """Cap 1 chung chi - IDEMPOTENT qua unique_together (employee, ref_type, ref_id): goi lai
    nhieu lan cho cung 1 ref tra ve ban ghi DA CAP, khong sinh PDF/tao moi lan 2 (khong cap
    trung)."""
    from .models import CertificateIssued

    existing = CertificateIssued.objects.filter(employee=employee, ref_type=ref_type, ref_id=ref_id).first()
    if existing:
        return existing

    issue_date = timezone.now().date()
    code = _generate_cert_code()
    pdf_bytes = build_certificate_pdf(template, {
        'recipient_name': employee.name,
        'program_or_course_name': program_or_course_name,
        'completion_line': completion_line,
        'issue_date': issue_date.strftime('%d/%m/%Y'),
        'cert_code': code,
    })
    pdf_url = upload_pdf_bytes(pdf_bytes, 'certificates', f'cert_{employee.code}')
    return CertificateIssued.objects.create(
        tenant=employee.tenant, employee=employee, template=template, program=program,
        ref_type=ref_type, ref_id=ref_id, issue_date=issue_date, code=code, pdf_url=pdf_url,
    )


def reissue_certificate(certificate):
    """'Cấp lại' (admin) - sinh lại PDF (vd sau khi sua toa do fields_config) nhung GIU nguyen
    code/issue_date cu (khong tao ban ghi moi - van la chung chi da cap tu truoc)."""
    pdf_bytes = build_certificate_pdf(certificate.template, {
        'recipient_name': certificate.employee.name,
        'program_or_course_name': _ref_name(certificate),
        'completion_line': _completion_line(certificate),
        'issue_date': certificate.issue_date.strftime('%d/%m/%Y'),
        'cert_code': certificate.code,
    })
    certificate.pdf_url = upload_pdf_bytes(pdf_bytes, 'certificates', f'cert_{certificate.employee.code}')
    certificate.save(update_fields=['pdf_url'])
    return certificate


def _ref_name(certificate):
    from .models import CertificateIssued

    if certificate.ref_type == CertificateIssued.RefType.COURSE:
        from courses.models import Course

        obj = Course.objects.filter(id=certificate.ref_id).first()
        return obj.title if obj else ''
    if certificate.ref_type == CertificateIssued.RefType.ASSESSMENT:
        from exams.models import Assessment

        obj = Assessment.objects.filter(id=certificate.ref_id).first()
        return obj.title if obj else ''
    return certificate.program.name if certificate.program else ''


PROGRAM_TYPE_COMPLETION_LINES = {
    'chuyen_mon': 'ĐÃ HOÀN THÀNH ĐÀO TẠO KỸ NĂNG NGHỀ',
    'bql': 'ĐÃ HOÀN THÀNH CHƯƠNG TRÌNH ĐÀO TẠO',
}


def _completion_line(certificate):
    from .models import CertificateIssued

    if certificate.ref_type == CertificateIssued.RefType.COURSE:
        return 'ĐÃ HOÀN THÀNH KHOÁ HỌC'
    if certificate.ref_type == CertificateIssued.RefType.ASSESSMENT:
        return 'ĐÃ HOÀN THÀNH BÀI THI'
    program_type = certificate.program.type if certificate.program else ''
    return PROGRAM_TYPE_COMPLETION_LINES.get(program_type, 'ĐÃ HOÀN THÀNH CHƯƠNG TRÌNH')


def _active_template(tenant, cert_type):
    from .models import CertificateTemplate

    return (
        CertificateTemplate.objects.filter(tenant=tenant, type=cert_type, active=True)
        .order_by('-created_at').first()
    )


def issue_course_certificate(enrollment):
    template = _active_template(enrollment.tenant, 'hoc')
    if not template:
        logger.warning(
            'issue_course_certificate: chưa có CertificateTemplate loại "hoc" đang active cho tenant %s - bỏ qua.',
            enrollment.tenant_id,
        )
        return None
    return issue_certificate(
        enrollment.employee, template, ref_type='course', ref_id=enrollment.course_id,
        program_or_course_name=enrollment.course.title, completion_line='ĐÃ HOÀN THÀNH KHOÁ HỌC',
    )


def issue_exam_certificate(attempt):
    template = _active_template(attempt.tenant, 'thi')
    if not template:
        logger.warning(
            'issue_exam_certificate: chưa có CertificateTemplate loại "thi" đang active cho tenant %s - bỏ qua.',
            attempt.tenant_id,
        )
        return None
    return issue_certificate(
        attempt.employee, template, ref_type='assessment', ref_id=attempt.assessment_id,
        program_or_course_name=attempt.assessment.title, completion_line='ĐÃ HOÀN THÀNH BÀI THI',
    )


def check_and_issue_programs(employee):
    """Goi sau moi moc co the lam doi dieu kien CertProgram (hoan thanh khoa/thi dat/xac nhan
    offline) - duyet CertProgram active cua tenant, cap chung chi cho chuong trinh vua du dieu
    kien (idempotent qua issue_certificate, tu bo qua chuong trinh da cap roi)."""
    from .models import CertProgram

    issued = []
    for program in CertProgram.objects.filter(tenant=employee.tenant, active=True):
        if not program.certificate_template:
            continue
        ok, _detail = program_eligible(employee, program)
        if not ok:
            continue
        line = PROGRAM_TYPE_COMPLETION_LINES.get(program.type, 'ĐÃ HOÀN THÀNH CHƯƠNG TRÌNH')
        cert = issue_certificate(
            employee, program.certificate_template, ref_type='program', ref_id=program.id,
            program=program, program_or_course_name=program.name, completion_line=line,
        )
        if cert:
            issued.append(cert)
    return issued


# ==================================================================== Hop cac diem hook (A+C+D)

def on_course_completed(enrollment):
    """Goi 1 lan khi 1 Enrollment CHUYEN sang COMPLETED (courses.services.save_lesson_progress
    hoac confirm_offline_completion) - chay ca dong bo ho so (A), log xAPI 'completed' (C), cap
    chung chi khoa + kiem CertProgram (D)."""
    sync_result_to_profile(enrollment)
    log_xapi(enrollment.employee, 'completed', 'course', enrollment.course_id)
    issue_course_certificate(enrollment)
    check_and_issue_programs(enrollment.employee)


def on_exam_finalized(attempt):
    """Goi 1 lan khi 1 Attempt CHUYEN GRADED (final) - tu exams.services.submit_attempt (khong
    co essay) hoac grade_attempt (co essay). Log xAPI passed/failed luon; CHI dong bo ho so +
    cap chung chi + kiem CertProgram khi DAT (dung trigger cua prompt: 'graded & passed')."""
    log_xapi(
        attempt.employee, 'passed' if attempt.passed else 'failed', 'assessment', attempt.assessment_id,
        result_json={
            'score': str(attempt.score) if attempt.score is not None else None,
            'percent': str(attempt.percent) if attempt.percent is not None else None,
            'passed': attempt.passed,
        },
    )
    if attempt.passed:
        sync_result_to_profile(attempt)
        issue_exam_certificate(attempt)
        check_and_issue_programs(attempt.employee)
