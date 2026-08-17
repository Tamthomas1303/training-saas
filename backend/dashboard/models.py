"""
Nen tang phan tich nang luc + Ho so 360 - Dashboard Phan A
(Prompt_Dashboard_A_NangLuc_HoSo360.md). Engine tinh diem (services.py) CHI DOC du lieu nguon
(courses.Enrollment/LessonProgress, exams.Attempt, evaluation.Evaluation/EvaluationDetail) -
KHONG ghi de, va KHONG dung toi employees.services.compute_final_result/recompute_final_result
(logic pass thu viec giu nguyen, an toan tuyet doi - xem services.py docstring).
"""
from decimal import Decimal

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


class ClsExamCompetencyMap(models.Model):
    """Anh xa ten bai thi ben CLS (cls_sync.ExamResult.exam_name) -> Competency - dung khi tinh
    diem nang luc tu nguon CLS, vi ExamResult khong co san FK toi Assessment/Competency (de thi
    CLS khong ton tai o he moi). Chua map (khong co dong nao voi exam_name do) -> engine bo qua
    dong gop cua bai thi do, khong doan (Prompt_Dashboard_A1_GanNhanNangLuc.md, muc 1)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='cls_exam_competency_maps')
    exam_name = models.CharField(max_length=255)
    competency = models.ForeignKey(
        Competency, on_delete=models.SET_NULL, related_name='cls_exam_maps', null=True, blank=True,
    )

    class Meta:
        unique_together = ('tenant', 'exam_name')
        ordering = ['exam_name']

    def __str__(self):
        return f'{self.exam_name} -> {self.competency}'


class CompetencyScoringConfig(models.Model):
    """Trong so Ly thuyet/Thuc hanh khi cong don diem 1 nang luc tu 4 nguon (Prompt_Dashboard_
    A1_GanNhanNangLuc.md, muc 2) - 1 dong/tenant, mac dinh 50/50 neu tenant chua tao dong nao
    (xem services.py::get_scoring_weights). Luu duoi dang % (0-100), KHONG bat buoc tong = 100 -
    engine tu chuan hoa (chia lai theo ty le) luc tinh diem."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='competency_scoring_config')
    theory_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('50'))
    practice_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('50'))

    def __str__(self):
        return f'{self.tenant_id} - LT {self.theory_weight}% / TH {self.practice_weight}%'


class TrainingCost(models.Model):
    """1 dong chi phi dao tao theo ky (Prompt_Dashboard_B_ManTongHop.md, muc 4) - nhap qua import
    CSV (xem services.py::import_training_costs) tu file mau File_HachToan_ChiPhiDaoTao_MAU.xlsx.
    Idempotent theo (thang, nam, loai chi phi, pham vi, ma don vi)."""

    class CostType(models.TextChoices):
        TRAINER_SALARY = 'trainer_salary', 'Lương & phụ cấp trainer'
        MATERIALS = 'materials', 'Tài liệu & in ấn'
        SOFTWARE = 'software', 'Phần mềm / LMS'
        FACILITIES = 'facilities', 'Cơ sở vật chất'
        TRAVEL = 'travel', 'Ăn ở & đi lại'
        OTHER = 'other', 'Khác'

    class Scope(models.TextChoices):
        SYSTEM = 'system', 'Toàn hệ thống'
        REGION = 'region', 'Vùng'
        RESTAURANT = 'restaurant', 'Nhà hàng'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='training_costs')
    month = models.IntegerField()
    year = models.IntegerField()
    cost_type = models.CharField(max_length=20, choices=CostType.choices)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.SYSTEM)
    # restaurants.Restaurant.code (scope=restaurant) hoac ten Vung (scope=region), rong neu
    # scope=system. Khong dung FK toi Restaurant vi "Vung" khong phai 1 model rieng trong he
    # thong nay (dung quy uoc chuoi tu do, giong Checklist.position/PositionTarget.position).
    unit_code = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = ('tenant', 'month', 'year', 'cost_type', 'scope', 'unit_code')
        ordering = ['-year', '-month']

    def __str__(self):
        return f'{self.month}/{self.year} - {self.cost_type} - {self.scope}:{self.unit_code} - {self.amount}'


class TrainingCostSource(models.Model):
    """Link CSV nguon chi phi dao tao (Google Sheet Publish to web > CSV), cau hinh tren giao
    dien - 1 dong/tenant, cung co che voi employees.RecruitmentSource. Rong = chua dung (cong
    cho chi phi hien 'Cho du lieu')."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='training_cost_source')
    csv_url = models.URLField(max_length=1000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'TrainingCostSource({self.tenant_id})'


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
