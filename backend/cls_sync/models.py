from django.db import models

from accounts.models import Tenant
from employees.models import Employee


class CourseResult(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='course_results')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='course_results')
    course_name = models.CharField(max_length=255)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, blank=True)
    cls_id = models.CharField(max_length=100, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.employee_id} - {self.course_name}'


class ExamResult(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='exam_results')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='exam_results')
    exam_name = models.CharField(max_length=255)
    attempt = models.IntegerField(default=1)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=False)
    cls_id = models.CharField(max_length=100, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'exam_name', 'attempt')

    def __str__(self):
        return f'{self.employee_id} - {self.exam_name} lần {self.attempt}'
