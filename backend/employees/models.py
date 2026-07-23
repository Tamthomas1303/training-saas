from django.db import models

from accounts.models import Tenant, User
from restaurants.models import Restaurant


class Employee(models.Model):
    class OperationUnit(models.TextChoices):
        PRODUCTION = 'production', 'Sản xuất'
        OFFICE = 'office', 'Văn phòng'
        RESTAURANT = 'restaurant', 'Nhà hàng'

    class EmployeeStatus(models.TextChoices):
        PROBATION = 'probation', 'Thử việc'
        ACTIVE = 'active', 'Chính thức'
        RESIGNED = 'resigned', 'Nghỉ việc'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='employees')
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=100, blank=True)
    operation_unit = models.CharField(max_length=20, choices=OperationUnit.choices, blank=True)
    job_level = models.CharField(max_length=100, blank=True)
    level_group = models.CharField(max_length=20, blank=True)
    start_date = models.DateField(null=True, blank=True)
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.SET_NULL, related_name='employees', null=True, blank=True
    )
    employee_status = models.CharField(
        max_length=20, choices=EmployeeStatus.choices, default=EmployeeStatus.PROBATION
    )
    probation_days = models.IntegerField(null=True, blank=True)
    skill_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    skill_result = models.CharField(max_length=50, blank=True)
    shift_ops = models.CharField(max_length=50, blank=True)
    # Cấp O (mục 7): kết quả hội đồng phỏng vấn
    interview_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    interview_result = models.CharField(max_length=50, blank=True)
    office_result = models.CharField(max_length=50, blank=True)
    final_result = models.CharField(max_length=50, blank=True)
    trainer = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='trainees', null=True, blank=True
    )
    commission_status = models.CharField(max_length=50, blank=True)
    retrain_deadline = models.DateField(null=True, blank=True)
    # Phieu ket qua thu viec da xuat (PDF) - luu lai de lan sau vao xem hien link ngay thay vi
    # phai xuat lai; xuat lai se xoa file cu va thay bang URL moi. Port phan hoi "Phan 1".
    probation_result_pdf_url = models.URLField(max_length=500, blank=True)
    # Nhân sự CŨ (nạp từ Data_LichSu/lộ trình, không thuộc luồng onboarding hệ mới). True = cũ,
    # False = nhân sự mới (onboarding từ 1/7, có trong DB_BACKUP). Dùng để tách danh sách theo dõi.
    is_legacy = models.BooleanField(default=False)

    class Meta:
        unique_together = ('tenant', 'code')

    def __str__(self):
        return f'{self.code} - {self.name}'


class RecruitmentSource(models.Model):
    """Link CSV nguồn tuyển dụng cấu hình trên giao diện (Cách 3) — 1 dòng/tenant.
    Lệnh sync_recruitment và nút 'Đồng bộ ngay' đọc link từ đây (không cần vào GitHub)."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='recruitment_source')
    csv_url = models.URLField(max_length=1000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'RecruitmentSource({self.tenant_id})'


class HrSyncSource(models.Model):
    """Link CSV cho từng tab của Google Sheet 'Auto Syncing - HR Data' (v2.1). Mỗi tenant có
    nhiều dòng, mỗi dòng ứng với một tab (roster cũ, lộ trình cấp S, đào tạo BQL, khóa học,
    đánh giá...). Lệnh đồng bộ đọc link ở đây, tự tìm dòng tiêu đề và map về đúng đích."""

    class Kind(models.TextChoices):
        LICHSU = 'lichsu', 'Data_LichSu (nhân sự cũ)'
        BACKUP = 'backup', 'DB_BACKUP (nhân sự mới từ 1/7)'
        LOTRINH = 'lotrinh', 'Quanly_Lotrinh (vị trí đã pass cấp S)'
        BQL = 'bql', 'Daotao_BQL (đào tạo/đánh giá cấp O)'
        DANHGIA = 'danhgia', 'Input_DanhGia_BQL (đánh giá cấp O)'
        COURSES = 'courses', 'Raw_Data_Khoa_Hoc (tham gia khóa)'
        MALOP = 'malop', 'Ma_Khoa_Hoc (danh mục khóa)'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='hr_sync_sources')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    csv_url = models.URLField(max_length=1000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('tenant', 'kind')

    def __str__(self):
        return f'HrSyncSource({self.tenant_id}, {self.kind})'


class MgmtDevelopment(models.Model):
    """Hồ sơ phát triển Ban quản lý / cấp O (nạp từ Daotao_BQL). Gom: nội dung đã đào tạo,
    điểm thi theo vai, đánh giá, trạng thái sẵn sàng (Target_Code/Final_Status)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='mgmt_developments')
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='mgmt_dev')
    target_code = models.CharField(max_length=20, blank=True)     # GS / BP / BTr / QL
    final_status = models.CharField(max_length=100, blank=True)   # "SẴN SÀNG (GS)" ...
    employee_source = models.CharField(max_length=100, blank=True)
    data = models.JSONField(default=dict, blank=True)             # train topics, scores, assessments
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'MgmtDev({self.employee_id}, {self.target_code})'


class LevelUpEnrollment(models.Model):
    """Đợt đào tạo thăng tiến (v2.1 / M1): nhân sự học MỘT vị trí mới (BQL chọn) để lên major
    level (S1→S2→S3). Hoàn thành 1 vị trí = lên 1 level; đủ 3 vị trí (gồm vị trí vào làm) → S3."""

    class Status(models.TextChoices):
        REGISTERED = 'registered', 'Đăng ký'
        TRAINING = 'training', 'Đang đào tạo'
        COMPLETED = 'completed', 'Hoàn thành (lên level)'
        FAILED = 'failed', 'Không đạt'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='level_up_enrollments')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='level_up_enrollments')
    target_position = models.CharField(max_length=100)
    zone = models.CharField(max_length=10, blank=True)          # FOH / BOH
    from_level = models.CharField(max_length=10, blank=True)     # major level lúc đăng ký (S1/S2)
    target_level = models.CharField(max_length=10, blank=True)   # major level đích (S2/S3)
    exam_batch = models.CharField(max_length=20, blank=True)     # vd 2026-T4 / 2026-T8 / 2026-T12
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REGISTERED)
    registered_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='level_up_registered', null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.employee_id} → {self.target_position} ({self.target_level})'
