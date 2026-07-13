from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class Checklist(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='checklists')
    brand = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    day = models.IntegerField(null=True, blank=True)
    category = models.CharField(max_length=100, blank=True)
    task_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    doc_url = models.URLField(blank=True)
    level_group = models.CharField(max_length=20, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.task_name


class TrainingProgress(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chưa bắt đầu'
        IN_PROGRESS = 'in_progress', 'Đang thực hiện'
        DONE = 'done', 'Hoàn thành'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='training_progress')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='training_progress')
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE, related_name='progress_entries')
    trainer = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='training_progress', null=True, blank=True
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    img_tailieu = models.URLField(max_length=500, blank=True)
    img_lythuyet = models.URLField(max_length=500, blank=True)
    img_thuchanh = models.URLField(max_length=500, blank=True)
    sign_trainer = models.URLField(max_length=500, blank=True)
    sign_trainee = models.URLField(max_length=500, blank=True)
    pdf_url = models.URLField(max_length=500, blank=True)
    note = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'checklist')

    def __str__(self):
        return f'{self.employee_id} - {self.checklist_id}'


class Document(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    file_url = models.URLField()
    category = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
