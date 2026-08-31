from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models


class Tenant(models.Model):
    class Plan(models.TextChoices):
        FREE = 'free', 'Free'
        PRO = 'pro', 'Pro'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'

    name = models.CharField(max_length=255)
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.FREE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        OM = 'om', 'OM'
        BOD = 'bod', 'BOD'
        AM = 'am', 'AM'
        KCS = 'kcs', 'KCS'
        BQL = 'bql', 'BQL'
        TRAINER = 'trainer', 'Trainer'
        # Tai khoan hoc vien (module Khoa hoc truc tuyen, MVP dot 1) - gan qua Employee.user,
        # KHONG phai vai tro quan ly. Pham vi API bi gioi han qua
        # accounts.permissions.EmployeeLearnerScope (chi /api/courses/, /api/auth/me).
        EMPLOYEE = 'employee', 'Học viên'

    class JobTitle(models.TextChoices):
        QLNH = 'qlnh', 'Quản lý nhà hàng'
        GIAM_SAT = 'giam_sat', 'Giám sát'
        BEP_TRUONG = 'bep_truong', 'Bếp trưởng'
        BEP_PHO = 'bep_pho', 'Bếp phó'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        INACTIVE = 'inactive', 'Inactive'
        LOCKED = 'locked', 'Locked'

    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE, related_name='users', null=True, blank=True
    )
    # Pham vi nha hang cho BQL/Trainer/KCS (port AuthService.gs::getScope). Admin/OM/BOD/AM
    # khong dung truong nay - vai tro cua ho la "toan he thong" (xem employees/permissions.py).
    restaurant = models.ForeignKey(
        'restaurants.Restaurant', on_delete=models.SET_NULL, related_name='staff_users',
        null=True, blank=True,
    )
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TRAINER)
    job_title = models.CharField(max_length=20, choices=JobTitle.choices, blank=True, null=True)
    trainer_zone = models.CharField(max_length=100, blank=True, null=True)
    google_email = models.EmailField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    avatar_url = models.URLField(max_length=500, blank=True)
    # Nhom 1 muc C.3 (Prompt_Nhom1_NhanSu_NguoiDung.md) - dat True khi Admin reset mat khau tam;
    # ep doi mat khau o lan dang nhap ke tiep (xem ChangePasswordView, MeView/UserSerializer).
    must_change_password = models.BooleanField(default=False)
    # Nhom 1 muc D.1 - "Luu tru" (an khoi danh sach, GIU nguyen du lieu trong DB, khoi phuc duoc)
    # - KHAC voi status='inactive' (nghi viec/ngung hoat dong van con hien trong danh sach mac
    # dinh, chi loc rieng qua UI). None = khong luu tru (mac dinh, hien binh thuong).
    archived_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.tenant_id})"


class PasswordSetToken(models.Model):
    """Nhom 3A (Prompt_Nhom3A_Onboarding_TuDong.md muc 1/3) - token 1 lan de nguoi dung dat mat
    khau lan dau (tai khoan tao tu dong khi onboarding, set_unusable_password luc tao - xem
    employees.automation.run_onboarding_for_new); co the tai dung cho "quen mat khau" sau nay.
    Token ngau nhien duy nhat, het han (mac dinh 72h - xem employees.automation), dung 1 lan
    (used_at)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_set_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        from django.utils import timezone

        return self.used_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f'PasswordSetToken({self.user_id})'


class BrandSettings(models.Model):
    """Cau hinh thuong hieu (UI dot 1 - Prompt_UI_Dot1_Theme.md muc 3c): mau/logo/ten he thong
    ap dung runtime cho MOI tai khoan cua tenant. OneToOne theo Tenant o dot nay (chua thuc su
    da-brand - `brand_key` de san cho tuong lai neu can tach nhieu thuong hieu trong CUNG 1
    tenant, hien khong dung de loc gi ca)."""

    class ThemeMode(models.TextChoices):
        LIGHT = 'light', 'Light'
        DARK = 'dark', 'Dark'

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='brand_settings')
    system_name = models.CharField(max_length=255, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)
    favicon_url = models.URLField(max_length=500, blank=True)
    brand_hex = models.CharField(max_length=7, default='#1e6f5c')
    brand_key = models.CharField(max_length=50, blank=True, null=True)
    theme_mode = models.CharField(max_length=10, choices=ThemeMode.choices, default=ThemeMode.LIGHT)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.tenant_id} - {self.brand_hex}'


class UserRestaurantAssignment(models.Model):
    """"Phan vung" cho KCS - 1 KCS co the phu trach nhieu nha hang. Port DB_AreaAssignment
    (UserService.gs::setUserAreas). Chi dung cho KCS hien tai (xem employees/permissions.py::
    get_restaurant_scope); User.restaurant (FK don) van la scope cho BQL/Trainer nhu truoc."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='restaurant_assignments')
    restaurant = models.ForeignKey(
        'restaurants.Restaurant', on_delete=models.CASCADE, related_name='assigned_users'
    )

    class Meta:
        unique_together = ('user', 'restaurant')

    def __str__(self):
        return f'{self.user_id} -> {self.restaurant_id}'


class GradingConfig(models.Model):
    """UI dot 3 (Prompt_UI_Dot3_CaiDat_GradingConfig.md muc B) - externalize cac tham so nghiep
    vu TRUOC DAY hardcode rai rac (diem dat thi/ky nang, trong so cong thuc, so ngay theo cap,
    phu cap, dieu kien chung chi) ve 1 noi CAU HINH DUOC qua man Cai dat, khong can sua code.

    Gia tri mac dinh cua CAC TRUONG DUOI DAY (field default o model) PHAI khop dung hang so dang
    hardcode HIEN TAI de dam bao KHONG doi ket qua nghiep vu (regression) khi lan dau bat ky
    tenant nao duoc doc qua accounts.services.get_grading_config() (tu tao ban ghi neu chua co).
    Voi cac truong TRUOC DAY doc tu bien moi truong (COMMISSION_*), get_grading_config() uu tien
    seed tu GIA TRI DANG CHAY THAT cua bien moi truong do (khong phai default() o day) luc tao
    ban ghi dau tien - de dung voi MOI deployment, ke ca deployment da tung chinh .env khac
    mac dinh trong settings.py (xem accounts/services.py)."""

    class KpiMode(models.TextChoices):
        SESSIONS = 'sessions', 'Đếm số buổi'
        HOURS = 'hours', 'Đếm giờ đào tạo'

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='grading_config')

    # Muc 11 (Prompt_Muc11_KPI_Gio.md muc 1) - cong tac che do KPI. Mac dinh 'sessions' = dem so
    # buoi (hanh vi HIEN HANH, khong doi gi). 'hours' kich hoat kpi.services.kpi_hours_stats +
    # cac field standard_minutes (checklist.Document)/duration_minutes (kpi.KpiSession)/
    # kpi.KpiHourTarget - xem kpi/services.py.
    kpi_mode = models.CharField(max_length=10, choices=KpiMode.choices, default=KpiMode.SESSIONS)

    # Nhom "Thi" - Chấm thi đạt/không (exams: employees.services.exam_pass/batch_lms_marks,
    # cls_sync, integration 'course_exam', career.py, employees/detail.py).
    exam_pass_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('80'))
    # Nhom "Ky nang" - hien chi la truong luu cau hinh (chua co ham dung rieng ngoai allowance_*
    # o duoi, vi trong code that hien tai nguong ky nang CHI duoc dung boi luong phu cap - xem
    # allowance_skill_min). Giu de du bang B cua prompt + san sang cho tuong lai.
    skill_pass_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('85'))

    # Nhom "Diem tong hop" - phieu ket qua thu viec (employees.detail.export_probation_result_pdf).
    weight_exam = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.4'))
    weight_practice = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('0.6'))

    # Nhom "Nang luc (radar)" - fallback khi tenant CHUA co CompetencyScoringConfig rieng (xem
    # dashboard.services.get_scoring_weights - CompetencyScoringConfig van la nguon uu tien neu
    # da ton tai, KHONG doi hanh vi do).
    weight_theory = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('50'))
    weight_practical = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('50'))

    # Nhom "Lo trinh" - han "dung lo trinh" theo cap (kpi.services._kpi_tier_days).
    days_staff = models.PositiveIntegerField(default=15)
    days_supervisor_deputy = models.PositiveIntegerField(default=30)
    days_manager_chef = models.PositiveIntegerField(default=60)

    # Mo ta ngưỡng thu viec (khong dung tinh toan tu dong o dot nay - chi de tham chieu/ghi chu
    # quy che, xem prompt muc B "probation_pass_rule (mo ta/nguong)").
    probation_pass_rule = models.TextField(
        blank=True,
        default=(
            '5 điều kiện hoa hồng trainer: hoàn thành LMS + thi đạt (exam_pass_percent) + '
            'checklist đào tạo 100% + đánh giá kỹ năng đạt (skill_pass_percent) + làm đủ '
            '1 tháng.'
        ),
    )

    # Nhom "Phu cap" - kpi.services.recompute_commission.
    allowance_per_person = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('300000'))
    allowance_exam_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('80'))
    allowance_skill_min = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('85'))
    # Danh sach Restaurant.code duoc ap dung hoa hong; RONG = ap dung TAT CA nha hang (dung mac
    # dinh HIEN TAI cua settings.COMMISSION_RESTAURANT_ALLOWLIST trong he thong nay - KHONG phai
    # "4 co so Kampong" cua ban Apps Script goc, xem ghi chu trong settings.py).
    allowance_scope = models.JSONField(default=list, blank=True)

    # Nhom "Chung chi" - integration.services.program_eligible (rule kind='positions_count').
    cert_positions_required = models.PositiveIntegerField(default=3)
    cert_program_rule = models.TextField(
        blank=True,
        default='Đủ số vị trí tối thiểu (cert_positions_required) đã hoàn thành để đạt điều kiện chương trình chứng chỉ theo vị trí.',
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='+', null=True, blank=True)

    def __str__(self):
        return f'GradingConfig({self.tenant_id})'


class GradingConfigHistory(models.Model):
    """1 dong = 1 lan doi 1 field cua GradingConfig - xem accounts.services.update_grading_config
    (PUT /api/settings/grading/ ghi 1 dong cho MOI field thuc su doi gia tri)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='grading_config_history')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='+', null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    field = models.CharField(max_length=50)
    old_value = models.CharField(max_length=500, blank=True)
    new_value = models.CharField(max_length=500, blank=True)
    # Snapshot TOAN BO GradingConfig NGAY SAU lan doi nay (JSON) - de doi chieu/khoi phuc du khong
    # co API "revert" o dot nay.
    snapshot_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.tenant_id} - {self.field}: {self.old_value} -> {self.new_value}'


class EmailSettings(models.Model):
    """UI dot 3 (Prompt_UI_Dot3_CaiDat_GradingConfig.md muc A2) - cau hinh NGUOI NHAN + LICH GUI
    bao cao dao tao qua email. KHONG co SMTP/mat khau/khoa o day (giu nguyen o bien moi truong
    EMAIL_* - xem config/settings.py) - dung y "Rang buoc bao mat" cua prompt.

    LUU Y: dot nay CHI luu cau hinh (nguoi nhan/lich) de nhap qua UI; CHUA dung 1 tien trinh tu
    dong (cron/scheduler) de THAT SU gui theo dung lich da luu - viec gui van qua
    reports.views.TrainingReportSendView (goi tay/kich hoat tu noi khac) nhu truoc. Tu dong hoa
    theo lich la viec rieng, ngoai pham vi dot 3 (xem bao cao ban giao)."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='email_settings')
    from_display_name = models.CharField(max_length=255, blank=True, default='Phòng Đào tạo')
    recipients = models.JSONField(default=list, blank=True)
    cc = models.JSONField(default=list, blank=True)
    weekly_enabled = models.BooleanField(default=False)
    weekly_weekday = models.PositiveSmallIntegerField(default=0)  # 0=Thu Hai .. 6=Chu Nhat
    weekly_hour = models.PositiveSmallIntegerField(default=8)
    monthly_enabled = models.BooleanField(default=False)
    monthly_day = models.PositiveSmallIntegerField(default=1)
    monthly_hour = models.PositiveSmallIntegerField(default=8)
    timezone = models.CharField(max_length=50, default='Asia/Ho_Chi_Minh')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'EmailSettings({self.tenant_id})'


class RoleMenuConfig(models.Model):
    """Muc 16 Phase 1 phan B (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md) - BAT/TAT the menu theo
    vai tro. 1 dong = 1 (tenant, role) DA duoc Admin cau hinh rieng - vai tro CHUA co dong nao
    o day nghia la "chua cau hinh", frontend tu dung mac dinh hien hanh (config/menu.js::
    ROLE_MENU + config/adminNav.js) KHONG doi gi (xem accounts.services.list_role_menu_config).
    `menu_keys` la danh sach DUONG DAN ROUTE (path, vd '/kpi') duoc BAT cho vai tro do - dung
    path lam khoa vi moi muc menu (ca menu.js lan adminNav.js) da co san path duy nhat, khong
    can them 1 bo khoa rieng phai dong bo tay giua backend/frontend.

    CHI dieu khien HIEN THI, KHONG noi quyen: mot path co the duoc BAT cho vai tro von khong co
    trong ProtectedRoute cua route do - the se hien nhung vao se bi chan (xem App.jsx). Xem them
    accounts.services.ADMIN_CORE_MENU_PATHS (cac path Admin luon duoc giu, tranh tu khoa minh)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='role_menu_configs')
    role = models.CharField(max_length=20, choices=User.Role.choices)
    menu_keys = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='+', null=True, blank=True)

    class Meta:
        unique_together = ('tenant', 'role')

    def __str__(self):
        return f'RoleMenuConfig({self.tenant_id}, {self.role})'


class RoleMenuConfigHistory(models.Model):
    """1 dong = 1 lan doi menu_keys cua 1 vai tro - xem accounts.services.update_role_menu_config
    (PUT /api/settings/role-menu/)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='role_menu_config_history')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='+', null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    role = models.CharField(max_length=20)
    old_keys = models.JSONField(default=list, blank=True)
    new_keys = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f'{self.tenant_id} - {self.role}: {len(self.old_keys)} -> {len(self.new_keys)} muc'


class PushSubscription(models.Model):
    """Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 3) - dang ky web push (PushManager.subscribe() phia
    trinh duyet, xem frontend src/utils/push.js) cho 1 tai khoan da dang nhap. 1 user co the co
    NHIEU subscription (nhieu thiet bi/trinh duyet). endpoint la duy nhat toan he thong (URL rieng
    do trinh duyet/push service cap cho tung subscription) - dung lam khoa update_or_create khi
    subscribe lai (vd sau khi trinh duyet tu lam moi subscription)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_subscriptions')
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'PushSubscription({self.user_id})'
