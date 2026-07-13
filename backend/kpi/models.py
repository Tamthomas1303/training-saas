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
