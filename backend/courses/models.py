"""
Nen tang Khoa hoc truc tuyen - MVP Dot 1/3 (Module_KhoaHoc_KyThi_Spec_v0.3.md). Dot nay CHI lam
khung khoa hoc + hoc + theo doi tien do. Ngan hang cau hoi/de thi = Dot 2. Dong bo ho so nhan su
(CourseResult), hoan thanh offline co nguoi xac nhan, log xAPI, chung chi, chong tua = Dot 3 - chi
de san FIELD da ghi ro (Course.competency_tag, Lesson.anti_seek, LessonProgress.completed_offline).

Video KHONG di qua Django - chi luu URL (R2/YouTube/Vimeo). Anh bia/PDF tai lieu dung
checklist/storage.py (upload_data_url) nhu cac app khac.
"""
from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class Course(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Nháp'
        PUBLISHED = 'published', 'Xuất bản'
        ARCHIVED = 'archived', 'Lưu trữ'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='courses')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cover_url = models.URLField(max_length=500, blank=True)
    objective = models.TextField(blank=True)
    target_audience = models.CharField(max_length=255, blank=True)
    est_minutes = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='courses_created', null=True, blank=True,
    )
    # Forward-compat Dot 2/3: gan nhan nang luc cho khoa hoc. CHUA co logic gi dung den o Dot 1.
    competency_tag = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class CourseModule(models.Model):
    """Chuong trong 1 khoa hoc."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='course_modules')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.course_id} - {self.title}'


class Lesson(models.Model):
    """Bai hoc trong 1 chuong."""

    class Type(models.TextChoices):
        VIDEO_R2 = 'video_r2', 'Video (R2)'
        VIDEO_YOUTUBE = 'video_youtube', 'Video (YouTube)'
        VIDEO_VIMEO = 'video_vimeo', 'Video (Vimeo)'
        PDF = 'pdf', 'PDF'
        TEXT = 'text', 'Văn bản'
        LINK = 'link', 'Liên kết'

    class CompleteRule(models.TextChoices):
        WATCH_PCT = 'watch_pct', 'Xem đủ % video'
        OPEN = 'open', 'Mở bài là xong'
        MARK = 'mark', 'Tự đánh dấu hoàn thành'
        QUIZ = 'quiz', 'Làm bài kiểm tra'  # Dot 2 (ngan hang cau hoi) moi dung duoc

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='lessons')
    module = models.ForeignKey(CourseModule, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=Type.choices)
    content_url = models.URLField(max_length=500, blank=True)
    content_html = models.TextField(blank=True)
    duration_sec = models.IntegerField(null=True, blank=True)
    # Co chong tua - PLAYER chong tua thuc su lam o Dot 3, dot nay chi luu co.
    anti_seek = models.BooleanField(default=False)
    complete_rule = models.CharField(max_length=20, choices=CompleteRule.choices, default=CompleteRule.MARK)
    pass_watch_pct = models.IntegerField(default=80)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.module_id} - {self.title}'


class Enrollment(models.Model):
    """Ghi danh 1 nhan su vao 1 khoa hoc."""

    class Status(models.TextChoices):
        ASSIGNED = 'assigned', 'Đã gán'
        IN_PROGRESS = 'in_progress', 'Đang học'
        COMPLETED = 'completed', 'Hoàn thành'

    class Source(models.TextChoices):
        MANUAL = 'manual', 'Gán tay'
        AUTO = 'auto', 'Tự động'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='course_enrollments')
    assigned_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='enrollments_assigned', null=True, blank=True,
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ASSIGNED)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('course', 'employee')

    def __str__(self):
        return f'{self.employee_id} - {self.course_id}'


class LessonProgress(models.Model):
    """Tien do 1 nhan su o 1 bai hoc, trong pham vi 1 lan ghi danh."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Chưa bắt đầu'
        IN_PROGRESS = 'in_progress', 'Đang học'
        DONE = 'done', 'Hoàn thành'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='lesson_progresses')
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='progresses')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progresses')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    watched_pct = models.IntegerField(default=0)
    last_position_sec = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Forward-compat Dot 3: hoan thanh offline co nguoi xac nhan (khong qua player). Dot 1 luon False.
    completed_offline = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')

    def __str__(self):
        return f'{self.enrollment_id} - {self.lesson_id}'
