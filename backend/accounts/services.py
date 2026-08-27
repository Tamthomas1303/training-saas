"""
GradingConfig (UI dot 3 - Prompt_UI_Dot3_CaiDat_GradingConfig.md muc B): 1 cho DUY NHAT de cac
app khac (exams/kpi/commission/integration/dashboard) DOC tham so nghiep vu, thay vi rai hang so
hardcode khap noi. get_grading_config() la ham DUY NHAT nen goi (khong rai
GradingConfig.objects.get() khap noi - dung y prompt) - co cache nhe trong process, tu invalidate
khi update_grading_config() ghi thay doi.
"""
import logging

from django.core.cache import cache

from .models import EmailSettings, GradingConfig, GradingConfigHistory

logger = logging.getLogger(__name__)

_GRADING_CONFIG_CACHE_TTL = 300
_HISTORY_FIELDS = [
    'exam_pass_percent', 'skill_pass_percent', 'weight_exam', 'weight_practice',
    'weight_theory', 'weight_practical', 'days_staff', 'days_supervisor_deputy',
    'days_manager_chef', 'probation_pass_rule', 'allowance_per_person', 'allowance_exam_min',
    'allowance_skill_min', 'allowance_scope', 'cert_positions_required', 'cert_program_rule',
]


def _cache_key(tenant_id):
    return f'grading_config:{tenant_id}'


def get_grading_config(tenant):
    """Tra ve GradingConfig cua tenant (tu tao ban ghi neu chua co - xem seed tu bien moi
    truong o duoi de dam bao KHONG doi ket qua nghiep vu so voi truoc khi co man Cai dat)."""
    cached = cache.get(_cache_key(tenant.id))
    if cached is not None:
        return cached

    from decimal import Decimal

    from django.conf import settings

    config, _created = GradingConfig.objects.get_or_create(
        tenant=tenant,
        defaults={
            # Cac truong nay TRUOC DAY doc tu bien moi truong (settings.COMMISSION_*) - seed tu
            # GIA TRI DANG CHAY THAT (khong phai default() khai bao o model) de dung voi MOI
            # deployment, ke ca deployment da tung chinh .env khac voi mac dinh trong settings.py.
            # Boc Decimal(str(...)) - COMMISSION_* la float (settings.py parse os.environ bang
            # float()) - tranh gan thang float vao DecimalField (sai kieu du lieu trong memory
            # cho toi khi refresh_from_db, anh huong ca lam tron va chuoi hien trong History).
            'exam_pass_percent': Decimal(str(settings.COMMISSION_EXAM_THRESHOLD)),
            'skill_pass_percent': Decimal(str(settings.COMMISSION_SKILL_THRESHOLD)),
            'allowance_per_person': Decimal(str(settings.COMMISSION_AMOUNT)),
            'allowance_exam_min': Decimal(str(settings.COMMISSION_EXAM_THRESHOLD)),
            'allowance_skill_min': Decimal(str(settings.COMMISSION_SKILL_THRESHOLD)),
            'allowance_scope': list(settings.COMMISSION_RESTAURANT_ALLOWLIST or []),
        },
    )
    cache.set(_cache_key(tenant.id), config, _GRADING_CONFIG_CACHE_TTL)
    return config


def invalidate_grading_config_cache(tenant_id):
    cache.delete(_cache_key(tenant_id))


def update_grading_config(tenant, user, changes):
    """changes: dict {field: gia_tri_moi} (chi cac field hop le trong _HISTORY_FIELDS). Ghi 1
    dong GradingConfigHistory cho MOI field THUC SU doi gia tri (bo qua field gui len nhung
    trung gia tri cu). Tra ve (config, so_dong_history_da_ghi)."""
    config = get_grading_config(tenant)
    changed_fields = []

    for field, new_value in changes.items():
        if field not in _HISTORY_FIELDS:
            continue
        old_value = getattr(config, field)
        # So sanh bang gia tri (KHONG phai str()) - old_value/new_value co the la Decimal o
        # 2 scale khac nhau (vd Decimal('80.0') vs Decimal('80.00')) nhung VAN bang nhau ve
        # gia tri; Decimal ho tro so sanh == truc tiep voi int/float nen an toan voi ca gia
        # tri chua qua serializer (xem cac noi goi ham nay truc tiep, khong qua PUT).
        if old_value == new_value:
            continue
        setattr(config, field, new_value)
        changed_fields.append((field, old_value, new_value))

    if not changed_fields:
        return config, 0

    config.updated_by = user
    config.save()
    invalidate_grading_config_cache(tenant.id)

    from .serializers import GradingConfigSerializer

    snapshot = GradingConfigSerializer(config).data
    GradingConfigHistory.objects.bulk_create([
        GradingConfigHistory(
            tenant=tenant, changed_by=user, field=field,
            old_value=str(old_value), new_value=str(new_value), snapshot_json=snapshot,
        )
        for field, old_value, new_value in changed_fields
    ])
    return config, len(changed_fields)


def get_email_settings(tenant):
    settings_obj, _created = EmailSettings.objects.get_or_create(tenant=tenant)
    return settings_obj


# ============================================================ Nhom 1 muc C/D (Prompt_Nhom1_
# NhanSu_NguoiDung.md) - man Nguoi dung: dat lai mat khau tam + luu tru/xoa cung tai khoan.

def generate_temp_password():
    """Mat khau tam ngau nhien khi Admin reset cho user quen mat khau - CHI tra ve 1 LAN de
    Admin copy dua cho user (khong luu dang doc duoc - DB chi giu ban hash qua set_password,
    giong moi mat khau khac)."""
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    # 12 ky tu ngau nhien du manh, tranh ky tu de nham (l/1/O/0) de Admin doc/go lai cho user
    # khong bi loi neu can nhap tay thay vi copy-paste.
    alphabet = ''.join(c for c in alphabet if c not in 'l1O0')
    return ''.join(secrets.choice(alphabet) for _ in range(12))


def reset_user_password(user):
    """Sinh mat khau tam, dat cho user + bat co must_change_password (ep doi o lan dang nhap
    ke tiep - xem ChangePasswordView). Tra ve mat khau tam (plaintext) DE ADMIN XEM 1 LAN NGAY
    LUC NAY - goi ham nay xong PHAI tra ve luon cho response, khong luu lai o dau khac."""
    password = generate_temp_password()
    user.set_password(password)
    user.must_change_password = True
    user.save(update_fields=['password', 'must_change_password'])
    return password


def archive_user(user):
    from django.utils import timezone

    user.archived_at = timezone.now()
    user.save(update_fields=['archived_at'])
    return user


def restore_user(user):
    user.archived_at = None
    user.save(update_fields=['archived_at'])
    return user


# (model, field_tren_model_tro_toi_User, nhan hien thi loi) - danh sach cac noi "da phat sinh
# du lieu dao tao/thi/hoa hong/danh gia" tham chieu toi 1 User (tai khoan nhan vien quan tri/
# trainer...), dung de CHAN xoa cung (muc D.2). Liet ke tuong minh (khong tu do quet moi FK
# trong project) de chi chan dung nhung tham chieu THAT SU la "du lieu nghiep vu" - loai tru cac
# FK chi la audit metadata (vd GradingConfigHistory.changed_by, da SET_NULL, khong phai du lieu
# dao tao/thi/danh gia theo dung nghia prompt muc D.2).
def _user_delete_blockers():
    from checklist.models import TrainingProgress
    from courses.models import Enrollment
    from employees.models import Employee, LevelUpEnrollment, TalentReview
    from evaluation.models import Evaluation
    from exams.models import AssessmentAssignment, Answer
    from kpi.models import Commission, KpiSession

    return [
        (Employee, 'trainer', 'đang là trainer phụ trách nhân sự'),
        (TrainingProgress, 'trainer', 'đã ghi nhận đào tạo (checklist)'),
        (KpiSession, 'trainer', 'đã tổ chức buổi đào tạo KPI'),
        (Commission, 'trainer', 'có hoa hồng/phụ cấp trainer'),
        (Evaluation, 'evaluator', 'đã chấm đánh giá'),
        (Answer, 'graded_by', 'đã chấm bài thi'),
        (TalentReview, 'reviewed_by', 'đã đánh giá nhân sự nguồn'),
        (LevelUpEnrollment, 'registered_by', 'đã đăng ký lộ trình thăng tiến'),
        (Enrollment, 'assigned_by', 'đã gán khóa học'),
        (AssessmentAssignment, 'assigned_by', 'đã gán đề thi'),
    ]


def check_user_deletable(user):
    """Tra ve (True, '') neu XOA CUNG duoc (chua co du lieu nghiep vu nao tham chieu toi), hoac
    (False, ly_do) - ly_do liet ke RO cac loai du lieu con vuong (muc D.2: "tra loi ro neu vuong
    khoa ngoai"). Chi kiem cac FK CO Y NGHIA nghiep vu (xem _user_delete_blockers), khong phai
    quet toan bo FK trong DB (vd audit-only nhu updated_by/changed_by khong tinh)."""
    reasons = [
        label for model, field, label in _user_delete_blockers()
        if model.objects.filter(**{field: user}).exists()
    ]
    if reasons:
        return False, 'Tài khoản đã phát sinh dữ liệu (' + '; '.join(reasons) + '). Dùng Lưu trữ thay vì xóa cứng.'
    return True, ''


# ============================================================ Nhom 4 (Prompt_Nhom4_PWA_Push.md
# muc 3) - web push, gan vao sourcing.services.notify_users de moi thong bao trong he thong tu
# day (3A/3B/3C + enrollment/session/result) tu day nguoi dung ke ca khi chua mo web.

def send_web_push(user, title, body='', link=''):
    """Gui web push toi MOI PushSubscription cua user bang pywebpush. FAIL-SILENT HOAN TOAN -
    khong duoc phep lam hong request/luong goi no (notify_users). Thieu VAPID env hoac chua cai
    pywebpush -> chi log canh bao roi bo qua (he van chay binh thuong qua in-app/email). Gap
    404/410 (subscription het han, trinh duyet/OS da huy dang ky) -> tu dong xoa subscription do."""
    from django.conf import settings

    from .models import PushSubscription

    if not (settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY):
        return

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning('Web push: chưa cài pywebpush - bỏ qua (in-app/email vẫn hoạt động).')
        return

    subscriptions = list(PushSubscription.objects.filter(user=user))
    if not subscriptions:
        return

    import json

    payload = json.dumps({'title': title, 'body': body, 'link': link, 'icon': '/icon-192.png'})
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': settings.VAPID_SUBJECT},
            )
        except WebPushException as exc:
            status_code = getattr(exc.response, 'status_code', None)
            if status_code in (404, 410):
                sub.delete()
            else:
                logger.warning('Web push thất bại (user=%s): %s', user.id, exc)
        except Exception:  # noqa: BLE001
            logger.exception('Web push lỗi không xác định (user=%s).', user.id)
