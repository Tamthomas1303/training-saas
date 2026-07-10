from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class Evaluation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Chưa đánh giá'
        DONE = 'done', 'Đã đánh giá'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='evaluations')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='evaluations')
    evaluated_at = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f'Evaluation #{self.pk} - {self.employee_id}'


class Council(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='councils')
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='council_members')
    examiner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='council_memberships')
    note = models.TextField(blank=True)

    class Meta:
        unique_together = ('evaluation', 'examiner')

    def __str__(self):
        return f'{self.examiner_id} @ Evaluation #{self.evaluation_id}'


class EvaluationDetail(models.Model):
    class Criterion(models.TextChoices):
        THEORY = 'theory', 'Lý thuyết'
        PRACTICE = 'practice', 'Thực hành'
        ATTITUDE = 'attitude', 'Thái độ'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='evaluation_details')
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='details')
    council = models.ForeignKey(Council, on_delete=models.CASCADE, related_name='scores')
    criterion = models.CharField(max_length=20, choices=Criterion.choices)
    score = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('council', 'criterion')

    def __str__(self):
        return f'{self.criterion} = {self.score}'
