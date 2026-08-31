from django.db import models

from accounts.models import Tenant, User
from checklist.models import Document
from employees.models import Employee
from restaurants.models import Restaurant


class KpiSession(models.Model):
    """Buoi KPI dao tao (coaching) do BQL/Trainer/AM/KCS to chuc. Port DB_KPISession
    (KPIService.gs::saveSession) - 3 anh minh chung + tung nguoi tham gia tu ky."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='kpi_sessions')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='kpi_sessions')
    trainer = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='kpi_sessions_conducted', null=True,
    )
    topic = models.CharField(max_length=255)
    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, related_name='kpi_sessions', null=True, blank=True,
    )
    date = models.DateField()
    note = models.TextField(blank=True)
    img_tailieu = models.URLField(max_length=500, blank=True)
    img_lythuyet = models.URLField(max_length=500, blank=True)
    img_thuchanh = models.URLField(max_length=500, blank=True)
    pdf_url = models.URLField(max_length=500, blank=True)
    # Muc 11 (Prompt_Muc11_KPI_Gio.md muc 4) - chi duoc dien khi GradingConfig.kpi_mode='hours'
    # luc tao buoi (xem kpi/services.py::save_kpi_session); None = buoi tao khi con o che do
    # 'sessions' (khong tinh vao KPI gio, van tinh vao KPI so buoi nhu truoc).
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.topic} - {self.restaurant_id} - {self.date}'


class KpiParticipant(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='kpi_participants')
    session = models.ForeignKey(KpiSession, on_delete=models.CASCADE, related_name='participants')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='kpi_participations')
    sign_url = models.URLField(max_length=500, blank=True)

    class Meta:
        unique_together = ('session', 'employee')

    def __str__(self):
        return f'{self.employee_id} @ {self.session_id}'


class KpiHourTarget(models.Model):
    """Muc 11 (Prompt_Muc11_KPI_Gio.md muc 3) - muc tieu GIO dao tao/thang, ap theo vi tri/chuc
    danh cua nguoi to chuc (BQL - xem kpi.services.kpi_hours_stats, doi chieu qua
    User.job_title). `position` la chuoi khop voi danh muc employees.Position.name (Muc 16 Phase
    1); position='' = gia tri MAC DINH CHUNG dung khi vi tri chua dat rieng."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='kpi_hour_targets')
    position = models.CharField(max_length=100, blank=True)
    target_minutes_per_month = models.PositiveIntegerField()

    class Meta:
        unique_together = ('tenant', 'position')
        ordering = ['position']

    def __str__(self):
        return f'{self.position or "(mặc định)"} - {self.target_minutes_per_month} phút/tháng'


class Commission(models.Model):
    """Phu cap/Hoa hong trainer khi 1 nhan su moi hoan thanh du 5 dieu kien onboarding.
    Port DB_Commission (CommissionService.gs) - hoan toan doc lap voi KpiSession/KpiParticipant
    (2 tinh nang khac nhau trong ban goc, chi dung chung 1 tab UI)."""

    class Status(models.TextChoices):
        WAITING = 'waiting', 'Chờ'
        ELIGIBLE = 'eligible', 'Đủ điều kiện'
        RETRAIN = 'retrain', 'Đào tạo lại'
        PAID = 'paid', 'Đã chi'
        NA = 'na', 'Không áp dụng'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='commissions')
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='commission')
    trainer = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='commissions_earned', null=True, blank=True,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cond_lms = models.BooleanField(default=False)
    cond_exam = models.BooleanField(default=False)
    cond_training = models.BooleanField(default=False)
    cond_skill_eval = models.BooleanField(default=False)
    cond_worked_1month = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.WAITING)
    retrain_deadline = models.DateField(null=True, blank=True)
    month = models.IntegerField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.employee_id} - {self.status}'


class ExportedReport(models.Model):
    """URL PDF da xuat gan nhat cho 1 (tenant, loai phieu, thang, nam) - de man KPI hien nut
    "Xem" (mo lai phieu da luu) ma khong can xuat lai. Port Prompt v2.1 05-06/08/2026 muc D
    ("Luu URL phieu da xuat theo ky de xem lai bat ky luc nao")."""

    class Kind(models.TextChoices):
        KPI_BQL = 'kpi_bql', 'Báo cáo KPI BQL'
        ALLOWANCE = 'allowance', 'Phiếu phụ cấp trainer'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='exported_reports')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    month = models.IntegerField()
    year = models.IntegerField()
    pdf_url = models.URLField(max_length=500)
    exported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='exported_reports', null=True, blank=True,
    )
    exported_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'kind', 'month', 'year')

    def __str__(self):
        return f'{self.kind} {self.month}/{self.year} (tenant {self.tenant_id})'
