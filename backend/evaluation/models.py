from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class EvalType(models.TextChoices):
    """Loai phieu danh gia - dung chung cho EvaluationCriteria va Evaluation.

    Skill_BQL: BQL danh gia ky nang (phieu chinh, chi 1 lan/nhan su).
    AM_KCS: AM/KCS kiem tra random (chi ap dung cho nhan su DA qua Skill_BQL).
    Training/Admin: Phong Dao tao / Ban giam doc danh gia (dung chung logic voi AM_KCS).
    Council: Hoi dong danh gia cap quan ly (nhieu giam khao, tinh trung binh).
    """
    SKILL_BQL = 'Skill_BQL', 'BQL đánh giá kỹ năng'
    AM_KCS = 'AM_KCS', 'AM/KCS kiểm tra'
    TRAINING = 'Training', 'Phòng Đào tạo'
    ADMIN = 'Admin', 'Ban giám đốc'
    COUNCIL = 'Council', 'Hội đồng'


class EvaluationCriteria(models.Model):
    """Bo tieu chi danh gia - port DB_EvaluationCriteria (EvaluationService.gs::getCriteria).

    Cac truong brand/position/level_group/eval_type de trong = wildcard (khop moi gia tri),
    dung y logic goc: '!c.Brand || c.Brand===brandCode', v.v.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='evaluation_criteria')
    brand = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    level_group = models.CharField(max_length=20, blank=True)
    eval_type = models.CharField(max_length=20, choices=EvalType.choices, blank=True)
    section = models.CharField(max_length=100, blank=True)
    content = models.CharField(max_length=255)
    max_score = models.IntegerField(default=100)
    is_mandatory = models.BooleanField(default=False)
    require_photo = models.BooleanField(default=False)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name_plural = 'Evaluation criteria'

    def __str__(self):
        return self.content


class Evaluation(models.Model):
    """1 phieu danh gia cho 1 nhan su, boi 1 nguoi danh gia, theo 1 loai (Eval_Type).

    Hoi dong (Council) dung chung bang nay: moi giam khao la 1 dong rieng
    (employee, evaluator, eval_type='Council'), tong hop trung binh tinh o view rieng.
    """

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Nháp'
        DONE = 'done', 'Hoàn thành'

    class Result(models.TextChoices):
        PASS = 'pass', 'Đạt'
        FAIL = 'fail', 'Không đạt'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='evaluations')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='evaluations')
    evaluator = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='evaluations_given', null=True)
    eval_type = models.CharField(max_length=20, choices=EvalType.choices)
    date = models.DateField(null=True, blank=True)
    total_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    result = models.CharField(max_length=10, choices=Result.choices, blank=True)
    note = models.TextField(blank=True)
    sign_evaluator = models.URLField(max_length=500, blank=True)
    sign_trainee = models.URLField(max_length=500, blank=True)
    pdf_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.employee_id} - {self.eval_type} - {self.evaluator_id}'


class EvaluationDetail(models.Model):
    """1 dong diem cho 1 tieu chi trong 1 phieu danh gia.

    criteria_id la string tu do: co the la pk that cua EvaluationCriteria (dang str),
    hoac 'CL:<checklist_id>' khi tieu chi suy tu checklist (fallback), hoac
    'COUNCIL_TAYNGHE'/'COUNCIL_DAOTAO'/'COUNCIL_VANHANH' cho Hoi dong. Content/max_score/
    is_mandatory/require_photo duoc luu lai (denormalize) tren tung dong de PDF/hien thi
    khong phu thuoc viec tieu chi goc con ton tai hay khong.
    """

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='evaluation_details')
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='details')
    criteria_id = models.CharField(max_length=50)
    content = models.CharField(max_length=255)
    max_score = models.IntegerField(default=100)
    is_mandatory = models.BooleanField(default=False)
    require_photo = models.BooleanField(default=False)
    score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    photo_url = models.URLField(max_length=500, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = ('evaluation', 'criteria_id')

    def __str__(self):
        return f'{self.criteria_id} = {self.score}'
