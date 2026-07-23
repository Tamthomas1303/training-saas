from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class Program(models.Model):
    """Chương trình đào tạo nguồn / quản lý cấp trung (M2). Có checklist nội dung riêng."""

    class Audience(models.TextChoices):
        SOURCE = 'source', 'Nhân sự nguồn'
        MANAGEMENT = 'management', 'Quản lý cấp trung'
        OTHER = 'other', 'Khác'

    class Mode(models.TextChoices):
        OFFLINE = 'offline', 'Offline (điểm danh trực tiếp)'
        ONLINE = 'online', 'Online (học/thi trên nền tảng)'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='programs')
    name = models.CharField(max_length=255)
    audience = models.CharField(max_length=20, choices=Audience.choices, default=Audience.SOURCE)
    # Cổng chờ offline→online (v2.2): hình thức + link nguồn học/thi khi bật online.
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.OFFLINE)
    source_url = models.URLField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TrainingContent(models.Model):
    """Danh mục nội dung đào tạo (catalog) — Admin thêm/bớt theo thay đổi vận hành. Tách khỏi
    checklist nội dung của từng chương trình (ProgramContent). Dùng cho đào tạo BQL/nguồn."""

    class Category(models.TextChoices):
        COMMON = 'common', 'Chung / Nền tảng'
        FOH = 'foh', 'FOH'
        BOH = 'boh', 'BOH'
        MANAGEMENT = 'management', 'Quản lý'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='training_contents')
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, blank=True)           # có thể map Ma_Khoa_Hoc
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.COMMON)
    target_roles = models.CharField(max_length=200, blank=True)  # vd "GS; BP" / "QL; BTr"
    is_prerequisite = models.BooleanField(default=False)         # vd Train the trainer
    is_active = models.BooleanField(default=True)
    note = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class ProgramContent(models.Model):
    """Checklist nội dung của 1 chương trình: buổi / chủ đề / nội dung (admin tạo)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='program_contents')
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='contents')
    session_no = models.IntegerField(null=True, blank=True)   # buổi
    topic = models.CharField(max_length=255, blank=True)      # chủ đề
    content = models.CharField(max_length=500)                # nội dung
    doc_url = models.URLField(max_length=500, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.content


class Cohort(models.Model):
    """Đợt đào tạo offline của 1 chương trình (có nhiều buổi, danh sách học viên)."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Đang mở đăng ký'
        ONGOING = 'ongoing', 'Đang đào tạo'
        CLOSED = 'closed', 'Đã kết thúc'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='cohorts')
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='cohorts')
    name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='cohorts_created', null=True, blank=True
    )
    # QR cấp sự kiện (C): học viên quét, chọn chủ đề/buổi rồi điểm danh.
    qr_token = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class CohortSession(models.Model):
    """1 buổi học trong đợt — có mã QR để học viên tự quét điểm danh."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='cohort_sessions')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='sessions')
    session_no = models.IntegerField(null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    qr_token = models.CharField(max_length=64, blank=True, db_index=True)  # link tự điểm danh
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'session_no']

    def __str__(self):
        return f'{self.cohort_id} - buổi {self.session_no}'


class Enrollment(models.Model):
    """Học viên trong 1 đợt đào tạo nguồn/quản lý (Admin/BQL thêm tay)."""

    class Status(models.TextChoices):
        REGISTERED = 'registered', 'Đăng ký'
        STUDYING = 'studying', 'Đang học'
        COMPLETED = 'completed', 'Hoàn thành'
        FAILED = 'failed', 'Không đạt'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='cohort_enrollments')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='enrollments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='cohort_enrollments')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REGISTERED)
    result = models.CharField(max_length=50, blank=True)   # Đạt / Không đạt
    added_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='cohort_enrollments_added', null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('cohort', 'employee')

    def __str__(self):
        return f'{self.employee_id} @ {self.cohort_id}'


class Attendance(models.Model):
    """Điểm danh 1 buổi cho 1 học viên (tự quét QR hoặc người phụ trách chỉnh tay)."""

    class Method(models.TextChoices):
        SELF = 'self', 'Tự quét QR'
        MANUAL = 'manual', 'Người phụ trách'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='attendances')
    session = models.ForeignKey(CohortSession, on_delete=models.CASCADE, related_name='attendances')
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='attendances')
    present = models.BooleanField(default=True)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.SELF)
    checked_in_at = models.DateTimeField(null=True, blank=True)
    marked_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='attendances_marked', null=True, blank=True
    )

    class Meta:
        unique_together = ('session', 'enrollment')

    def __str__(self):
        return f'{self.enrollment_id} - buổi {self.session_id}'


class ContentProgress(models.Model):
    """Hoàn thành từng mục nội dung (ProgramContent) cho 1 học viên trong đợt."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='content_progress')
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='content_progress')
    content = models.ForeignKey(ProgramContent, on_delete=models.CASCADE, related_name='progress_entries')
    done = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('enrollment', 'content')

    def __str__(self):
        return f'{self.enrollment_id} - {self.content_id} = {self.done}'


class Notification(models.Model):
    """Thông báo in-app (đăng ký/lịch học/kết quả...). Email gửi song song ở M2.5."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='notifications')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=50, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
