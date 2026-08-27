"""
Nhom 3A (Prompt_Nhom3A_Onboarding_TuDong.md) - onboarding tu dong khi import nhan su MOI
(is_legacy=False): tao tai khoan (mat khau khong dung duoc + link dat mat khau) + auto-enroll
khoa hoi nhap (OnboardingCourseRule) + gui email tiep nhan cho QLNH nha hang. Theo dung 3 cong
tac AutomationSettings cua tenant - luong "co san" (recipe), KHONG phai builder tu do.

An toan: KHONG BAO GIO gui mat khau tho qua email (chi link dat mat khau qua PasswordSetToken,
token 1 lan + het han). SMTP/khoa email luon doc tu bien moi truong (config/settings.py EMAIL_*),
KHONG luu trong AutomationSettings.

Idempotent: goi lai cho 1 nhan su da co user se KHONG tao tai khoan/token moi (bo qua buoc 1 +
buoc 3, vi buoc 3 can token vua sinh); auto-enroll dung unique_together (course, employee) cua
Enrollment nen khong tao trung dong ghi danh.
"""
import logging
import secrets

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

PASSWORD_SET_TOKEN_TTL_HOURS = 72


def get_automation_settings(tenant):
    from .models import AutomationSettings

    settings_obj, _created = AutomationSettings.objects.get_or_create(tenant=tenant)
    return settings_obj


def _create_account(employee):
    """Tao User role EMPLOYEE gan employee.user (tach tu EmployeeCreateLoginView, KHAC o cho
    dung set_unusable_password + PasswordSetToken thay vi DEFAULT_PASSWORD - luong nay dua qua
    email, khong phai Admin doc mat khau truc tiep tu response). Tra ve (user, token)."""
    from accounts.models import PasswordSetToken, User

    base_username = (employee.code or f'nv{employee.id}').lower()
    username = base_username
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix += 1
        username = f'{base_username}{suffix}'

    user = User(username=username, tenant=employee.tenant, full_name=employee.name, role=User.Role.EMPLOYEE)
    user.set_unusable_password()
    user.save()
    employee.user = user
    employee.save(update_fields=['user'])

    token = PasswordSetToken.objects.create(
        user=user, token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + timezone.timedelta(hours=PASSWORD_SET_TOKEN_TTL_HOURS),
    )
    return user, token


def _enroll_onboarding_courses(employee):
    """Auto-enroll cac khoa hoi nhap (Course.status=published) khop employee.position (khop
    chuan hoa qua normalize_key, dong bo cach khop vi tri o cac noi khac trong employees).
    Idempotent qua get_or_create + unique_together (course, employee) cua Enrollment."""
    from courses.models import Course, Enrollment

    from .models import OnboardingCourseRule
    from .services import normalize_key

    position_key = normalize_key(employee.position)
    rules = OnboardingCourseRule.objects.filter(tenant=employee.tenant).select_related('course')
    enrolled_course_ids = []
    for rule in rules:
        if normalize_key(rule.position) != position_key:
            continue
        if rule.course.status != Course.Status.PUBLISHED:
            continue
        _enrollment, created = Enrollment.objects.get_or_create(
            tenant=employee.tenant, course=rule.course, employee=employee,
            defaults={'source': Enrollment.Source.AUTO},
        )
        if created:
            enrolled_course_ids.append(rule.course_id)
    return enrolled_course_ids


def _render_template(text, ctx):
    try:
        return (text or '').format(**ctx)
    except (KeyError, IndexError):
        return text or ''


def _send_welcome_email(employee, user, token, automation_settings):
    """Gui email tiep nhan toi QLNH nha hang cua nhan su (Restaurant.email - field co san,
    KHONG can them field moi) + CC theo cau hinh. KHONG gui neu nha hang chua co email (log
    canh bao, khong chan luong onboarding). KHONG BAO GIO kem mat khau tho - chi link dat mat
    khau. Log ket qua (thanh cong/loi), KHONG log token/email vao noi cong khai."""
    from django.core.mail import EmailMultiAlternatives

    to_email = (employee.restaurant.email or '').strip() if employee.restaurant_id else ''
    if not to_email:
        logger.warning('Onboarding NV %s: khong gui duoc email tiep nhan (nha hang chua co email).', employee.id)
        return False

    link = f"{settings.FRONTEND_URL.rstrip('/')}/set-password?token={token.token}"
    ctx = {
        'ten_nhan_su': employee.name,
        'ma_nhan_su': employee.code,
        'nha_hang': employee.restaurant.name if employee.restaurant_id else '',
        'vi_tri': employee.position or '',
        'link_dat_mat_khau': link,
        'ten_dang_nhap': user.username,
        'ten_he_thong': employee.tenant.name,
    }
    subject = _render_template(automation_settings.welcome_email_subject, ctx)
    body = _render_template(automation_settings.welcome_email_body, ctx)
    sender_name = (automation_settings.sender_display_name or '').strip()
    from_email = f'{sender_name} <{settings.DEFAULT_FROM_EMAIL}>' if sender_name else settings.DEFAULT_FROM_EMAIL
    cc = list(automation_settings.cc_recipients or [])

    msg = EmailMultiAlternatives(subject=subject, body=body, from_email=from_email, to=[to_email], cc=cc or None)
    try:
        msg.send(fail_silently=False)
    except Exception:  # noqa: BLE001
        logger.exception('Onboarding NV %s: gui email tiep nhan that bai.', employee.id)
        return False
    logger.info('Onboarding NV %s: da gui email tiep nhan thanh cong.', employee.id)
    return True


def run_onboarding_for_new(employee):
    """Goi cho MOI nhan su MOI vua import (is_legacy=False). Idempotent - an toan goi lai (vd
    import lai cung nhan su) khong tao trung tai khoan/enroll. Tra ve dict ket qua tung buoc de
    goi noi (vd management command) co the tong hop bao cao; khong raise - loi tung buoc duoc
    bat rieng (email) hoac tu nhien idempotent (tai khoan/enroll)."""
    if getattr(employee, 'is_legacy', False):
        return None

    cfg = get_automation_settings(employee.tenant)
    result = {'account_created': False, 'enrolled_courses': [], 'email_sent': False}

    user = employee.user
    token = None
    if cfg.auto_create_account and not user:
        user, token = _create_account(employee)
        result['account_created'] = True

    if cfg.auto_enroll_onboarding:
        result['enrolled_courses'] = _enroll_onboarding_courses(employee)

    if cfg.send_welcome_email and user and token:
        result['email_sent'] = _send_welcome_email(employee, user, token, cfg)

    return result


# ========================================================================================
# Nhom 3B (Prompt_Nhom3B_ThiThuViec_TuDong.md) - luong 4: tu gan thi ket thuc thu viec (co
# buoc CHO DUYET) + coi thi qua camera; luong 5: tu gui ket qua thu viec + moc luong.
# ========================================================================================

def _find_probation_exam_rule(tenant, position):
    """Tim ProbationExamRule khop vi tri (khop chuan hoa - dong bo cach khop cua
    OnboardingCourseRule/checklist). Tra ve None neu chua cau hinh cho vi tri nay."""
    from .models import ProbationExamRule
    from .services import normalize_key

    position_key = normalize_key(position)
    for rule in ProbationExamRule.objects.filter(tenant=tenant).select_related('assessment'):
        if normalize_key(rule.position) == position_key:
            return rule
    return None


def check_probation_exam_eligibility(employee):
    """Nhom 3B muc 2 (luong 4, buoc 1): kiem 1 nhan su co du dieu kien vao hang doi thi ket thuc
    thu viec chua - goi o 3 diem: hoan thanh khoa (courses.services._on_course_completed_safe),
    luu checklist dat 100% (checklist.services.save_training_progress), va quet hang ngay
    (management command scan_probation_exam_candidates). Idempotent qua
    ProbationExamCandidate.unique_together (employee, assessment) - KHONG tao lai neu da co ban
    ghi (du dang pending/approved/rejected). Tra ve ProbationExamCandidate MOI TAO, hoac None
    neu chua du dieu kien / da co san / cong tac tat / nhan su cu."""
    from .models import Employee, ProbationExamCandidate
    from .services import checklist_progress_percent, lms_done

    if getattr(employee, 'is_legacy', False):
        return None
    if employee.employee_status != Employee.EmployeeStatus.PROBATION:
        return None

    cfg = get_automation_settings(employee.tenant)
    if not cfg.auto_assign_probation_exam:
        return None
    if not lms_done(employee):
        return None
    if checklist_progress_percent(employee) != 100:
        return None

    rule = _find_probation_exam_rule(employee.tenant, employee.position)
    if not rule:
        return None

    candidate, created = ProbationExamCandidate.objects.get_or_create(
        employee=employee, assessment=rule.assessment,
        defaults={'tenant': employee.tenant, 'status': ProbationExamCandidate.Status.PENDING_APPROVAL},
    )
    if not created:
        return None

    if not cfg.require_approval_before_exam:
        approve_probation_exam_candidate(candidate, user=None)

    return candidate


def approve_probation_exam_candidate(
    candidate, user, exam_session_id=None, start_at=None, end_at=None,
    proctor_ids=None, supervised_by_restaurant_camera=False,
):
    """Duyet 1 ung vien: gan/kich hoat AssessmentAssignment de nhan su lam bai. exam_session_id
    (tuy chon) = dua vao 1 Ky thi CO SAN (phai cung de thi) - dung cho truong hop Phong DT da
    len lich san 1 dot thi chung. Khong truyen -> tu tao 1 ExamSession rieng cho 1 nhan su nay
    (start_at mac dinh = ngay bay gio, end_at = khong gioi han neu khong truyen).

    supervised_by_restaurant_camera=True (chi ap dung khi TU TAO session moi) -> bat luon
    Assessment.proctoring_enabled (webcam chup anh dinh ky lam bang chung, dung y muc 3 cua
    prompt) vi day la truong CHUNG tren Assessment, anh huong moi lan thi cua de do.

    user=None khi goi tu luong tu dong (require_approval_before_exam=False) - khong phai Admin/
    Trainer nao duyet, chi he thong tu xu ly ngay khi du dieu kien."""
    from django.utils import timezone

    from exams.models import AssessmentAssignment, ExamSession

    from .models import ProbationExamCandidate

    if candidate.status != ProbationExamCandidate.Status.PENDING_APPROVAL:
        raise ValueError('Ứng viên này đã được xử lý (không còn ở trạng thái chờ duyệt).')

    tenant = candidate.tenant
    if exam_session_id:
        session = ExamSession.objects.filter(
            tenant=tenant, pk=exam_session_id, assessment_id=candidate.assessment_id,
        ).first()
        if not session:
            raise ValueError('Không tìm thấy kỳ thi phù hợp (phải cùng đề thi kết thúc thử việc).')
    else:
        session = ExamSession.objects.create(
            tenant=tenant, title=f'Thi thử việc - {candidate.employee.name}',
            assessment=candidate.assessment,
            start_at=start_at or timezone.now(), end_at=end_at,
            target_config={'employee_ids': [candidate.employee_id]}, created_by=user,
            supervised_by_restaurant_camera=bool(supervised_by_restaurant_camera),
        )
        if proctor_ids:
            from accounts.models import User

            session.proctors.set(User.objects.filter(tenant=tenant, id__in=proctor_ids))
        if session.supervised_by_restaurant_camera and not candidate.assessment.proctoring_enabled:
            candidate.assessment.proctoring_enabled = True
            candidate.assessment.save(update_fields=['proctoring_enabled'])

    AssessmentAssignment.objects.get_or_create(
        assessment=candidate.assessment, employee=candidate.employee,
        defaults={'tenant': tenant, 'assigned_by': user, 'exam_session': session},
    )

    candidate.status = ProbationExamCandidate.Status.APPROVED
    candidate.exam_session = session
    candidate.decided_by = user
    candidate.decided_at = timezone.now()
    candidate.save(update_fields=['status', 'exam_session', 'decided_by', 'decided_at'])
    return candidate


def reject_probation_exam_candidate(candidate, user, reason=''):
    """Tu choi 1 ung vien - khong tao AssessmentAssignment, nhan su khong lam bai duoc."""
    from django.utils import timezone

    from .models import ProbationExamCandidate

    if candidate.status != ProbationExamCandidate.Status.PENDING_APPROVAL:
        raise ValueError('Ứng viên này đã được xử lý (không còn ở trạng thái chờ duyệt).')

    candidate.status = ProbationExamCandidate.Status.REJECTED
    candidate.decided_by = user
    candidate.decided_at = timezone.now()
    candidate.reject_reason = (reason or '').strip()
    candidate.save(update_fields=['status', 'decided_by', 'decided_at', 'reject_reason'])
    return candidate


def _salary_effective_date(cfg, decision_date):
    """Moc luong chinh thuc (Nhom 3B muc 4) theo AutomationSettings.salary_effective_rule:
    'pass_date' -> chinh la ngay Pass; 'next_month_first' -> ngay 1 cua thang KE TIEP sau ngay
    Pass (vd Pass 15/8 -> 1/9; Pass 31/12 -> 1/1 nam sau)."""
    import datetime

    from .models import AutomationSettings

    if not decision_date:
        return None
    if cfg.salary_effective_rule == AutomationSettings.SalaryEffectiveRule.NEXT_MONTH_FIRST:
        if decision_date.month == 12:
            return datetime.date(decision_date.year + 1, 1, 1)
        return datetime.date(decision_date.year, decision_date.month + 1, 1)
    return decision_date


def notify_probation_result_if_needed(employee, result, decision_date):
    """Nhom 3B luong 5 - goi tu employees.services (_notify_probation_result_safe) moi lan
    final_result CHUYEN thanh 'Pass thu viec' (result='pass', decision_date=pass_date) hoac
    nghi viec ngay tu luc dang thu viec (result='failed', decision_date=resigned_at - tien de
    gan nhat co that cho "chot Khong dat", xem ProbationResultNotification docstring).

    Idempotent: ProbationResultNotification.unique_together (employee, result, decision_date) -
    CHI gui 1 lan cho MOI quyet dinh cu the; goi lai (vd recompute_final_result goi rat nhieu
    noi) voi CUNG decision_date se khong gui lap. Tra ve ban ghi log (da gui hoac dang co san
    tu truoc), hoac None neu tat cong tac/khong co decision_date/nhan su cu."""
    from .models import AutomationSettings, ProbationResultNotification

    if getattr(employee, 'is_legacy', False) or not decision_date:
        return None
    cfg = get_automation_settings(employee.tenant)
    if not cfg.auto_send_probation_result:
        return None

    log_row, created = ProbationResultNotification.objects.get_or_create(
        employee=employee, result=result, decision_date=decision_date,
        defaults={'tenant': employee.tenant},
    )
    if not created:
        return log_row  # da gui cho quyet dinh nay roi - khong gui lap

    salary_date = _salary_effective_date(cfg, decision_date) if result == ProbationResultNotification.Result.PASS else None
    to_email = (employee.restaurant.email or '').strip() if employee.restaurant_id else ''
    if not to_email:
        logger.warning('Ket qua thu viec NV %s: khong gui duoc email (nha hang chua co email).', employee.id)
        return log_row

    ctx = {
        'ten_nhan_su': employee.name,
        'ma_nhan_su': employee.code,
        'nha_hang': employee.restaurant.name if employee.restaurant_id else '',
        'vi_tri': employee.position or '',
        'ket_qua': 'Pass thử việc' if result == ProbationResultNotification.Result.PASS else 'Không đạt',
        'ngay_pass': decision_date.strftime('%d/%m/%Y') if result == ProbationResultNotification.Result.PASS else '',
        'ngay_luong_chinh_thuc': salary_date.strftime('%d/%m/%Y') if salary_date else '',
        'ten_he_thong': employee.tenant.name,
    }
    subject = _render_template(cfg.result_email_subject, ctx)
    body = _render_template(cfg.result_email_body, ctx)
    sender_name = (cfg.sender_display_name or '').strip()
    from_email = f'{sender_name} <{settings.DEFAULT_FROM_EMAIL}>' if sender_name else settings.DEFAULT_FROM_EMAIL
    cc = list(cfg.cc_recipients or [])

    from django.core.mail import EmailMultiAlternatives

    msg = EmailMultiAlternatives(subject=subject, body=body, from_email=from_email, to=[to_email], cc=cc or None)
    try:
        msg.send(fail_silently=False)
    except Exception:  # noqa: BLE001
        logger.exception('Gui email ket qua thu viec that bai cho NV %s (%s).', employee.id, result)
        return log_row

    if salary_date:
        log_row.salary_effective_date = salary_date
        log_row.save(update_fields=['salary_effective_date'])
    logger.info('Da gui email ket qua thu viec cho NV %s (%s).', employee.id, result)
    return log_row
