from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class CourseResult(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='course_results')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='course_results')
    course_name = models.CharField(max_length=255)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=50, blank=True)
    # % tien do hoc tren CLS luc dong bo (user.progress) - dung lam fallback dieu kien du dieu
    # kien thi khi cot diem/status chua dong bo dung (xem cls_sync/services.py::onboarding_eligible).
    progress = models.IntegerField(null=True, blank=True)
    cls_id = models.CharField(max_length=100, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'course_name')

    def __str__(self):
        return f'{self.employee_id} - {self.course_name}'


class ExamResult(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='exam_results')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='exam_results')
    exam_name = models.CharField(max_length=255)
    # Ten day du cua bai thi (topic.name tren CLS, vd "15N - Ky thuat pha che...") - exam_name
    # van giu = candidate_type ("15N") de unique_together + logic nhom lan thi khong doi.
    exam_full_name = models.CharField(max_length=255, blank=True)
    # Ngay dien ra ky thi (exam.startDate/createdDate tren CLS - xem sync_cls.py::_parse_exam_date)
    # - dung de loc "trong ky" cho bao cao dao tao tuan/thang (reports app), KHONG phai ngay sync.
    exam_date = models.DateField(null=True, blank=True)
    attempt = models.IntegerField(default=1)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # Diem phuc khao (admin/Phong Dao tao sua tay, uu tien hon diem CLS goc) - score o tren
    # LUON la diem goc tu CLS, sync_cls khong bao gio dong den cot nay. Xem final_score.
    score_adjusted = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=False)
    cls_id = models.CharField(max_length=100, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('employee', 'exam_name', 'attempt')

    def __str__(self):
        return f'{self.employee_id} - {self.exam_name} lần {self.attempt}'

    @property
    def final_score(self):
        """Diem dung de tinh pass/hien thi o moi noi - uu tien diem phuc khao neu co."""
        return self.score_adjusted if self.score_adjusted is not None else self.score


class ExamScoreAdjustment(models.Model):
    """Audit log cho tung lan phuc khao diem thi (Task 2) - luu lai de doi chieu, khong sua/xoa."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='exam_score_adjustments')
    exam_result = models.ForeignKey(ExamResult, on_delete=models.CASCADE, related_name='adjustments')
    old_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    new_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reason = models.TextField(blank=True)
    adjusted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='exam_score_adjustments', null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'ExamScoreAdjustment({self.exam_result_id}, {self.old_score} -> {self.new_score})'
