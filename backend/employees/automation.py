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
