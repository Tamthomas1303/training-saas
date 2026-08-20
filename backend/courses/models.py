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
    # Forward-compat Dot 2/3: gan nhan nang luc cho khoa hoc (chu, chua dung logic gi). Dashboard
    # Phan A dung FK ben duoi thay the (uu tien FK theo dung prompt) - GIU LAI truong chu nay de
    # khong pha du lieu cu, khong con doc trong engine tinh diem nang luc.
    competency_tag = models.CharField(max_length=100, blank=True)
    # Dashboard Phan A: gan khoa hoc vao 1 nang luc trong khung (dashboard.Competency) - dung de
    # engine tinh diem nang luc (dashboard.services.compute_competency_scores) biet khoa nay
    # "nuoi" nang luc nao. Null = chua gan, khong tinh vao nang luc nao.
    competency = models.ForeignKey(
        'dashboard.Competency', on_delete=models.SET_NULL, related_name='courses', null=True, blank=True,
    )
    # Dot 3 phan A: ma dinh danh khoa nay ben he cu (CourseResult.course_name) - ADMIN TU GAN
    # TAY. Rong = KHONG dong bo (bo qua, log canh bao) - tranh doan bua anh huong pass thu viec.
    # Xem integration.services.sync_result_to_profile.
    sync_course_code = models.CharField(max_length=255, blank=True)
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
        SCORM = 'scorm', 'SCORM (Articulate 360...)'  # Dot 4 - xem ScormPackage

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
    # Co chong tua - CHI co y nghia voi type='video_r2' (Giai doan B,
    # Prompt_ChongGianLan_Thi_Video.md): bat ca chan tua vuot (LessonProgress.max_watched_sec)
    # LAN tu tam dung theo webcam khi mat khuon mat (dung 1 co, khong them toggle rieng).
    anti_seek = models.BooleanField(default=False)
    # Nguong tu tam dung theo webcam (giay) - CHI ap dung khi anti_seek=True + type=video_r2.
    face_pause_warn_sec = models.PositiveIntegerField(default=5)
    face_pause_stop_sec = models.PositiveIntegerField(default=10)
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
    # Giai doan B: "moc da xem toi da" - KHAC last_position_sec (vi tri con tro hien tai, co the
    # lui lai khi tua nguoc). Chi tang dan, server tu choi buoc nhay lon (xem
    # services.record_watch_progress) - la TRAN cho phep tua toi da o player (chan tua vuot that
    # su, khong chi dua vao JS client).
    max_watched_sec = models.IntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Forward-compat Dot 3: hoan thanh offline co nguoi xac nhan (khong qua player). Dot 1 luon False.
    completed_offline = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')

    def __str__(self):
        return f'{self.enrollment_id} - {self.lesson_id}'


class LessonWatchEvent(models.Model):
    """Log 'moc tam dung/tiep tuc' khi HOC (Giai doan B) - KHAC ProctoringEvent cua module thi:
    KHONG co truong anh (co tinh, dam bao cau truc "khong luu anh khi hoc" - xem
    Prompt_ChongGianLan_Thi_Video.md muc 'Chung: snapshot chi dung khi THI")."""

    class Type(models.TextChoices):
        PAUSED_FACE_LOST = 'paused_face_lost', 'Tự tạm dừng (mất khuôn mặt)'
        RESUMED = 'resumed', 'Tiếp tục phát'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='lesson_watch_events')
    lesson_progress = models.ForeignKey(LessonProgress, on_delete=models.CASCADE, related_name='watch_events')
    type = models.CharField(max_length=20, choices=Type.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.lesson_progress_id} - {self.type} @ {self.created_at}'


class ScormPackage(models.Model):
    """1 goi SCORM (zip đã giải nén) gan vao 1 Lesson type='scorm' - Dot 4.

    storage_prefix: thu muc R2 chua toan bo file cua goi (vd 'scorm/<tenant>/<uuid>/'),
    KHONG doi khi hoc vien hoc (chi doi khi admin upload lai). launch_path: duong dan file
    khoi chay (href cua resource scormtype='sco' trong imsmanifest.xml), tuong doi so voi
    storage_prefix - dung de dung URL noi dung: GET .../content/<launch_path>.
    """

    class Version(models.TextChoices):
        SCORM_12 = 'scorm_12', 'SCORM 1.2'
        SCORM_2004 = 'scorm_2004', 'SCORM 2004'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='scorm_packages')
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='scorm_package')
    version = models.CharField(max_length=20, choices=Version.choices)
    storage_prefix = models.CharField(max_length=500)
    launch_path = models.CharField(max_length=500)
    title = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='scorm_packages_uploaded', null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.lesson_id} - {self.version}'


class ScormTracking(models.Model):
    """Trang thai chay (cmi) cua 1 nhan su cho 1 bai SCORM, gan theo LessonProgress (1-1) -
    Dot 4. cmi_json luu TOAN BO cmi (runtimeData tu scorm-again CommitObject, dang json long -
    xem courses/views.py::ScormCommitView) de np lai luc resume (loadFromJSON ben client)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='scorm_trackings')
    lesson_progress = models.OneToOneField(LessonProgress, on_delete=models.CASCADE, related_name='scorm_tracking')
    cmi_json = models.JSONField(default=dict, blank=True)
    # completionStatus tu CommitObject (scorm-again) - da chuan hoa chung cho ca 2 phien ban:
    # 'completed' | 'incomplete' | 'not attempted' | 'unknown'. Xem ScormCommitView.
    lesson_status = models.CharField(max_length=20, blank=True)
    score_raw = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.lesson_progress_id} - {self.lesson_status}'
