from django.db import models

from accounts.models import Tenant, User
from restaurants.models import Restaurant


class Employee(models.Model):
    class OperationUnit(models.TextChoices):
        PRODUCTION = 'production', 'Sản xuất'
        OFFICE = 'office', 'Văn phòng'
        RESTAURANT = 'restaurant', 'Nhà hàng'

    class EmployeeStatus(models.TextChoices):
        PROBATION = 'probation', 'Thử việc'
        ACTIVE = 'active', 'Chính thức'
        RESIGNED = 'resigned', 'Nghỉ việc'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='employees')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=100, blank=True)
    operation_unit = models.CharField(max_length=20, choices=OperationUnit.choices, blank=True)
    job_level = models.CharField(max_length=100, blank=True)
    level_group = models.CharField(max_length=20, blank=True)
    start_date = models.DateField(null=True, blank=True)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.SET_NULL, related_name='employees', null=True, blank=True
    )
    employee_status = models.CharField(
        max_length=20, choices=EmployeeStatus.choices, default=EmployeeStatus.PROBATION
    )
    probation_days = models.IntegerField(null=True, blank=True)
    skill_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    skill_result = models.CharField(max_length=50, blank=True)
    shift_ops = models.CharField(max_length=50, blank=True)
    office_result = models.CharField(max_length=50, blank=True)
    final_result = models.CharField(max_length=50, blank=True)
    trainer = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='trainees', null=True, blank=True
    )
    commission_status = models.CharField(max_length=50, blank=True)
    retrain_deadline = models.DateField(null=True, blank=True)
    # Phieu ket qua thu viec da xuat (PDF) - luu lai de lan sau vao xem hien link ngay thay vi
    # phai xuat lai; xuat lai se xoa file cu va thay bang URL moi. Port phan hoi "Phan 1".
    probation_result_pdf_url = models.URLField(max_length=500, blank=True)

    class Meta:
        unique_together = ('tenant', 'code')

    def __str__(self):
        return f'{self.code} - {self.name}'
