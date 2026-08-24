"""
GradingConfig (UI dot 3 - Prompt_UI_Dot3_CaiDat_GradingConfig.md muc B): 1 cho DUY NHAT de cac
app khac (exams/kpi/commission/integration/dashboard) DOC tham so nghiep vu, thay vi rai hang so
hardcode khap noi. get_grading_config() la ham DUY NHAT nen goi (khong rai
GradingConfig.objects.get() khap noi - dung y prompt) - co cache nhe trong process, tu invalidate
khi update_grading_config() ghi thay doi.
"""
from django.core.cache import cache

from .models import EmailSettings, GradingConfig, GradingConfigHistory

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
