"""
Nen tang phan tich nang luc + Ho so 360 - Dashboard Phan A
(Prompt_Dashboard_A_NangLuc_HoSo360.md). Engine tinh diem (services.py) CHI DOC du lieu nguon
(courses.Enrollment/LessonProgress, exams.Attempt, evaluation.Evaluation/EvaluationDetail) -
KHONG ghi de, va KHONG dung toi employees.services.compute_final_result/recompute_final_result
(logic pass thu viec giu nguyen, an toan tuyet doi - xem services.py docstring).
"""
from django.db import models

from accounts.models import Tenant


class CompetencyGroup(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='competency_groups')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('tenant', 'code')

    def __str__(self):
        return f'{self.code} - {self.name}'


class Competency(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='competencies')
    group = models.ForeignKey(CompetencyGroup, on_delete=models.CASCADE, related_name='competencies')
    name = models.CharField(max_length=255)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('tenant', 'group', 'name')
        verbose_name_plural = 'Competencies'

    def __str__(self):
        return self.name


class PositionTarget(models.Model):
    """Diem muc tieu (0-100) cua 1 nang luc cho 1 vi tri. Khong co dong = khong ap dung ('—'
    trong file KhungNangLuc_MucTieu_TheoViTri) - radar bo qua truc do cho vi tri nay."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='position_targets')
    position = models.CharField(max_length=100)
    competency = models.ForeignKey(Competency, on_delete=models.CASCADE, related_name='position_targets')
    target_score = models.IntegerField()

    class Meta:
        unique_together = ('tenant', 'position', 'competency')

    def __str__(self):
        return f'{self.position} - {self.competency_id}: {self.target_score}'


class PositionGroupWeight(models.Model):
    """Trong so (%) cua 1 nhom nang luc cho 1 vi tri - dung tinh CI. File nguon gop chung A1+A2
    thanh 1 cot 'Chuyen mon (A)' (1 nguoi chi thuoc 1 tuyen bep/phuc vu) - luc import ghi CUNG
    trong so do vao CA group A1 va A2 (xem services.py::import_position_group_weights); vi CI
    chi cong nhom NAO CO DU LIEU nen group khong dung toi tu dong khong dong gop."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='position_group_weights')
    position = models.CharField(max_length=100)
    group = models.ForeignKey(CompetencyGroup, on_delete=models.CASCADE, related_name='position_weights')
    weight = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        unique_together = ('tenant', 'position', 'group')

    def __str__(self):
        return f'{self.position} - {self.group_id}: {self.weight}%'


class DashboardIndicator(models.Model):
    """Cau hinh 1 chi so tren dashboard (Phan A muc 5+6) - admin bat/tat + chinh nguong mau.
    Seed tu file ChiSo_Dashboard_ChonLua_v0.2.xlsx (cac dong CHON='x') qua management command
    seed_dashboard_indicators."""

    class Direction(models.TextChoices):
        HIGHER_BETTER = 'higher_better', 'Cao tốt'
        LOWER_BETTER = 'lower_better', 'Thấp tốt'
        NONE = 'none', 'Không tô màu (danh sách/biểu đồ)'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='dashboard_indicators')
    key = models.SlugField(max_length=100)
    label = models.CharField(max_length=255)
    group_label = models.CharField(max_length=100, blank=True)
    # Man hien thi: ['ho_so'] = Ho so 360, ['ceo'], ['gdt'] - 1 chi so co the thuoc nhieu man.
    role_scope = models.JSONField(default=list, blank=True)
    enabled = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    direction = models.CharField(max_length=20, choices=Direction.choices, default=Direction.NONE)
    green_threshold = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    yellow_threshold = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'key')
        ordering = ['order', 'id']

    def __str__(self):
        return f'{self.key} - {self.label}'
