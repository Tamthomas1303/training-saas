from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class KpiSession(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='kpi_sessions')
    name = models.CharField(max_length=255)
    session_date = models.DateField(null=True, blank=True)
    trainer = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='kpi_sessions', null=True, blank=True
    )
    pdf_url = models.URLField(blank=True)
    status = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class KpiParticipant(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='kpi_participants')
    session = models.ForeignKey(KpiSession, on_delete=models.CASCADE, related_name='participants')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='kpi_participations')
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    result = models.CharField(max_length=50, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = ('session', 'employee')

    def __str__(self):
        return f'{self.employee_id} @ {self.session_id}'


class Commission(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='commissions')
    trainer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='commissions')
    session = models.ForeignKey(
        KpiSession, on_delete=models.SET_NULL, related_name='commissions', null=True, blank=True
    )
    period = models.CharField(max_length=20, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f'{self.trainer_id} - {self.period}'
