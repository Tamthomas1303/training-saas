"""
Module Ky thi / Danh gia - MVP Dot 2/3 (Module_KhoaHoc_KyThi_Spec_v0.3.md). Dot nay lam ngan
hang cau hoi + de thi + lam bai + cham diem. Dot 3 moi dong bo ket qua ve ho so nhan su
(cls_sync.ExamResult), offline-confirm, xAPI, chung chi, proctoring, item analysis, import QTI,
cham diem mot phan - CHUA lam gi o day, chi de san field forward-compat (competency_tag, position).

Video/anh minh chung dung URL (R2/YouTube/Vimeo/upload_data_url), khong luu file qua Django.
"""
from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class QuestionBank(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='question_banks')
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Question(models.Model):
    class Type(models.TextChoices):
        SINGLE = 'single', 'Chọn 1 đáp án'
        MULTIPLE = 'multiple', 'Chọn nhiều đáp án'
        TRUEFALSE = 'truefalse', 'Đúng / Sai'
        TEXT_FILL = 'text_fill', 'Điền chữ'
        NUMERIC = 'numeric', 'Điền số'
        ESSAY = 'essay', 'Tự luận'
        MATCHING = 'matching', 'Nối cặp'
        DRAGDROP = 'dragdrop', 'Kéo-thả vào chỗ trống'

    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Dễ'
        MEDIUM = 'medium', 'Trung bình'
        HARD = 'hard', 'Khó'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='questions')
    bank = models.ForeignKey(QuestionBank, on_delete=models.CASCADE, related_name='questions')
    type = models.CharField(max_length=20, choices=Type.choices)
    stem_html = models.TextField()
    points = models.IntegerField(default=1)
    difficulty = models.CharField(max_length=10, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    explanation_html = models.TextField(blank=True)
    media_url = models.URLField(max_length=500, blank=True)
    # Forward-compat Dot 3 (gan nang luc/vi tri cho cau hoi) - CHUA co logic gi dung den o Dot 2.
    competency_tag = models.CharField(max_length=100, blank=True)
    position = models.CharField(max_length=100, blank=True)
    # Du lieu rieng theo dang (xem exams/services.py module docstring de biet cau truc tung dang):
    # text_fill: {accepted:[...], case_sensitive}. numeric: {answer, tolerance}. essay: {rubric?}.
    # matching: {pairs:[{left,right},...]}. dragdrop: {tokens:[...], gaps:[{id,answer},...]}.
    # single/multiple/truefalse dung QuestionOption, khong dung config.
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'[{self.type}] {self.stem_html[:60]}'


class QuestionOption(models.Model):
    """Dung cho Question.type = single/multiple/truefalse."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='question_options')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    order = models.IntegerField(default=0)
    content_html = models.TextField()
    is_correct = models.BooleanField(default=False)
    media_url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.question_id} - {self.content_html[:40]}'


class Assessment(models.Model):
    class ShowResultMode(models.TextChoices):
        IMMEDIATELY = 'immediately', 'Hiện ngay sau khi nộp'
        AFTER_CLOSE = 'after_close', 'Hiện sau khi đề đóng (lưu trữ)'
        SCORE_ONLY = 'score_only', 'Chỉ hiện điểm, không hiện đáp án'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Nháp'
        PUBLISHED = 'published', 'Xuất bản'
        ARCHIVED = 'archived', 'Lưu trữ (đóng đề)'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='assessments')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    time_limit_min = models.IntegerField(null=True, blank=True)
    pass_mark = models.IntegerField(default=80)
    max_attempts = models.IntegerField(default=1)
    shuffle_questions = models.BooleanField(default=True)
    shuffle_options = models.BooleanField(default=True)
    show_result_mode = models.CharField(
        max_length=20, choices=ShowResultMode.choices, default=ShowResultMode.IMMEDIATELY,
    )
    # Rut cau ngau nhien khi bat dau attempt, thay vi chon tay qua AssessmentQuestion. Cau truc
    # (tu chon, MVP): {"bank_id": <id>, "count": <n>, "difficulty": "<easy|medium|hard>"?}.
    # difficulty bo trong = khong loc do kho. rong/None = dung cau chon tay (AssessmentQuestion).
    random_pool_config = models.JSONField(null=True, blank=True)
    # Forward-compat Dot 3. Dashboard Phan A dung FK ben duoi thay the (uu tien FK) - giu lai
    # truong chu de khong pha du lieu cu, khong con dung trong engine tinh diem nang luc.
    competency_tag = models.CharField(max_length=100, blank=True)
    # Dashboard Phan A: gan de thi vao 1 nang luc trong khung - xem
    # dashboard.services.compute_competency_scores. Null = chua gan.
    competency = models.ForeignKey(
        'dashboard.Competency', on_delete=models.SET_NULL, related_name='assessments', null=True, blank=True,
    )
    # Dot 3 phan A: ma dinh danh bai thi nay ben he cu (ExamResult.exam_name) - ADMIN TU GAN
    # TAY. Rong = KHONG dong bo (bo qua, log canh bao) - tranh doan bua anh huong pass thu viec.
    # Xem integration.services.sync_result_to_profile.
    sync_exam_type = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='assessments_created', null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class AssessmentQuestion(models.Model):
    """Cau CHON TAY trong 1 de - bo qua neu Assessment dung random_pool_config."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='assessment_questions')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='assessment_questions')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='+')
    order = models.IntegerField(default=0)
    points_override = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['order']
        unique_together = ('assessment', 'question')

    def __str__(self):
        return f'{self.assessment_id} - {self.question_id}'


class AssessmentAssignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = 'assigned', 'Đã gán'
        DONE = 'done', 'Đã thi'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='assessment_assignments')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='assignments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='assessment_assignments')
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='assessment_assignments_made', null=True, blank=True,
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('assessment', 'employee')

    def __str__(self):
        return f'{self.employee_id} - {self.assessment_id}'


class Attempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = 'in_progress', 'Đang làm'
        SUBMITTED = 'submitted', 'Đã nộp (chờ chấm tự luận)'
        GRADED = 'graded', 'Đã chấm xong'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='attempts')
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='attempts')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='exam_attempts')
    attempt_no = models.IntegerField()
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    # Danh sach id cau hoi CHO LAN THI NAY, theo dung thu tu da tron/rut (can luu lai de cau hoi
    # + thu tu on dinh xuyen suot attempt, ke ca khi rut ngau nhien tu random_pool_config).
    question_ids = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('assessment', 'employee', 'attempt_no')
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.employee_id} - {self.assessment_id} (lần {self.attempt_no})'


class Answer(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='exam_answers')
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='+')
    # Dap an nguoi thi nhap, cau truc theo dang - xem exams/services.py::grade_objective_answer.
    response_json = models.JSONField(default=dict, blank=True)
    auto_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    manual_score = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    is_correct = models.BooleanField(null=True, blank=True)
    graded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='exam_answers_graded', null=True, blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('attempt', 'question')

    def __str__(self):
        return f'{self.attempt_id} - {self.question_id}'
