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
    # Ngay final_result chuyen thanh "Pass thu viec" (dung de tinh luong) - set 1 lan khi
    # chuyen trang thai, xoa neu roi khoi Pass. Xem recompute_final_result.
    pass_date = models.DateField(null=True, blank=True)
    # Ngay chuyen sang employee_status='resigned' - set 1 lan, xoa neu roi khoi resigned. Dung
    # de bao cao dao tao tuan/thang dem so nghi viec TRONG KY. Xem change_employee_status.
    resigned_at = models.DateField(null=True, blank=True)
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
    # Tai khoan dang nhap cua CHINH nhan su nay (module Khoa hoc truc tuyen, MVP dot 1) - null =
    # chua tao. Tao qua employees/views.py::EmployeeCreateLoginView (role=User.Role.EMPLOYEE,
    # pham vi API bi gioi han qua accounts.permissions.EmployeeLearnerScope).
    user = models.OneToOneField(
        User, on_delete=models.SET_NULL, related_name='employee', null=True, blank=True,
    )

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


class TalentReview(models.Model):
    """G3 — cổng AM/KCS phỏng vấn đánh giá sẵn sàng TRƯỚC khi nhân sự (đủ 3 vị trí) chính thức
    vào danh sách nhân sự nguồn. Duyệt = vào nguồn; từ chối = chưa vào."""

    class Decision(models.TextChoices):
        PENDING = 'pending', 'Chờ đánh giá'
        APPROVED = 'approved', 'Duyệt vào nguồn'
        REJECTED = 'rejected', 'Chưa sẵn sàng'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='talent_reviews')
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='talent_review')
    decision = models.CharField(max_length=20, choices=Decision.choices, default=Decision.PENDING)
    note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='talent_reviews_done', null=True, blank=True
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'TalentReview({self.employee_id}, {self.decision})'


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


class AutomationSettings(models.Model):
    """Nhom 3A (Prompt_Nhom3A_Onboarding_TuDong.md muc 1/4) - 3 cong tac bat/tat + tham so cho
    luong onboarding tu dong khi import nhan su moi (is_legacy=False, chua co user). SMTP/khoa
    email GIU o bien moi truong (config/settings.py EMAIL_*) - o day CHI dat nguoi nhan/mau/ten
    hien thi, KHONG BAO GIO luu thong tin dang nhap SMTP. Nguoi nhan CHINH cua email tiep nhan =
    email cua Restaurant (QLNH phu trach nha hang nhan su, field co san Restaurant.email) -
    cc_recipients chi la CC THEM (vd phong DT)."""

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='automation_settings')
    auto_create_account = models.BooleanField(default=False)
    auto_enroll_onboarding = models.BooleanField(default=False)
    send_welcome_email = models.BooleanField(default=False)
    welcome_email_subject = models.CharField(
        max_length=255, blank=True, default='Chào mừng {ten_nhan_su} gia nhập {ten_he_thong}',
    )
    welcome_email_body = models.TextField(
        blank=True,
        default=(
            'Xin chào {ten_nhan_su},\n\n'
            'Bạn đã được tạo tài khoản đào tạo tại {ten_he_thong} (mã nhân sự {ma_nhan_su}, '
            'nhà hàng {nha_hang}, vị trí {vi_tri}).\n\n'
            'Tên đăng nhập: {ten_dang_nhap}\n'
            'Vui lòng đặt mật khẩu lần đầu tại: {link_dat_mat_khau}\n\n'
            'Trân trọng.'
        ),
    )
    sender_display_name = models.CharField(max_length=255, blank=True, default='Phòng Đào tạo')
    cc_recipients = models.JSONField(default=list, blank=True)

    # ---- Nhom 3B (Prompt_Nhom3B_ThiThuViec_TuDong.md muc 1) - luong 4 (tu gan thi ket thuc thu
    # viec, co cho duyet) + luong 5 (tu gui ket qua + moc luong). ----
    class SalaryEffectiveRule(models.TextChoices):
        PASS_DATE = 'pass_date', 'Ngày Pass thử việc'
        NEXT_MONTH_FIRST = 'next_month_first', 'Ngày 1 tháng kế tiếp'

    auto_assign_probation_exam = models.BooleanField(default=False)
    # Mac dinh True (dung y prompt): KHONG auto cho thi ngay ke ca khi auto_assign bat - luon
    # dung lai o "Cho duyet thi" tru khi Admin CHU DONG tat co nay.
    require_approval_before_exam = models.BooleanField(default=True)
    auto_send_probation_result = models.BooleanField(default=False)
    salary_effective_rule = models.CharField(
        max_length=20, choices=SalaryEffectiveRule.choices, default=SalaryEffectiveRule.PASS_DATE,
    )
    result_email_subject = models.CharField(
        max_length=255, blank=True, default='Kết quả thử việc: {ten_nhan_su} - {ket_qua}',
    )
    result_email_body = models.TextField(
        blank=True,
        default=(
            'Kính gửi nhà hàng {nha_hang},\n\n'
            'Nhân sự {ten_nhan_su} (mã {ma_nhan_su}, vị trí {vi_tri}) có kết quả thử việc: {ket_qua}.\n'
            'Ngày Pass: {ngay_pass}\n'
            'Ngày lương chính thức: {ngay_luong_chinh_thuc}\n\n'
            'Trân trọng, {ten_he_thong}.'
        ),
    )

    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='+', null=True, blank=True)

    def __str__(self):
        return f'AutomationSettings({self.tenant_id})'


class OnboardingCourseRule(models.Model):
    """Anh xa vi tri -> khoa hoi nhap de auto-enroll khi onboarding tu dong (Nhom 3A muc 1/2) -
    1 vi tri co the co nhieu khoa (nhieu dong). course dung string ref 'courses.Course' de tranh
    circular import (courses/models.py da import employees.models.Employee)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='onboarding_course_rules')
    position = models.CharField(max_length=100)
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='onboarding_rules')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'position', 'course')

    def __str__(self):
        return f'{self.position} -> {self.course_id}'


class ProbationExamRule(models.Model):
    """Anh xa vi tri -> de thi ket thuc thu viec (Nhom 3B muc 1) - 1 vi tri = 1 de (khac
    OnboardingCourseRule vi 1 vi tri chi nen co 1 bai thi ket thuc thu viec). assessment dung
    string ref 'exams.Assessment' de tranh circular import (exams/models.py da import
    employees.models.Employee)."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='probation_exam_rules')
    position = models.CharField(max_length=100)
    assessment = models.ForeignKey(
        'exams.Assessment', on_delete=models.CASCADE, related_name='probation_exam_rules',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('tenant', 'position')

    def __str__(self):
        return f'{self.position} -> {self.assessment_id}'


class ProbationExamCandidate(models.Model):
    """Hang doi 'Cho duyet thi' (Nhom 3B muc 2) - 1 dong sinh ra khi 1 nhan su du dieu kien thi
    ket thuc thu viec (is_legacy=False, dang probation, lms_done + checklist=100%, co
    ProbationExamRule khop vi tri) - xem employees.automation.check_probation_exam_eligibility.
    unique_together (employee, assessment) VUA la rang buoc nghiep vu (1 nhan su chi co 1 hang
    doi cho 1 de) VUA la khoa idempotency (khong tao lai neu da co ban ghi, du dang pending/
    approved/rejected)."""

    class Status(models.TextChoices):
        PENDING_APPROVAL = 'pending_approval', 'Chờ duyệt'
        APPROVED = 'approved', 'Đã duyệt'
        REJECTED = 'rejected', 'Từ chối'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='probation_exam_candidates')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='probation_exam_candidates')
    assessment = models.ForeignKey(
        'exams.Assessment', on_delete=models.CASCADE, related_name='probation_exam_candidates',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_APPROVAL)
    # Gan khi duyet (approve_probation_exam_candidate) - ExamSession chua khung gio [start_at,
    # end_at] de nhan su lam bai (xem exams.models.ExamSession).
    exam_session = models.ForeignKey(
        'exams.ExamSession', on_delete=models.SET_NULL, related_name='probation_exam_candidates',
        null=True, blank=True,
    )
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='+', null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'assessment')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee_id} - {self.assessment_id} ({self.status})'


class ProbationResultNotification(models.Model):
    """Log + khoa idempotency cho Luong 5 (Nhom 3B muc 4) - 1 dong = 1 lan DA gui email ket qua
    thu viec cho 1 "quyet dinh" cu the cua 1 nhan su. decision_date = pass_date (khi Pass) hoac
    resigned_at (khi nghi viec ngay tu luc dang thu viec - tien de gan nhat co that trong he
    thong hien tai cho "chot Khong dat", vi Employee chua co trang thai rieng cho truong hop
    nay). unique_together (employee, result, decision_date) chan gui LAP moi lan
    recompute_final_result goi lai (rat nhieu noi goi ham nay) cho CUNG 1 quyet dinh, nhung VAN
    cho gui lai neu sau nay phat sinh 1 quyet dinh MOI voi decision_date khac (vd thu viec lai)."""

    class Result(models.TextChoices):
        PASS = 'pass', 'Pass thử việc'
        FAILED = 'failed', 'Không đạt'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='probation_result_notifications')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='probation_result_notifications')
    result = models.CharField(max_length=10, choices=Result.choices)
    decision_date = models.DateField()
    salary_effective_date = models.DateField(null=True, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'result', 'decision_date')

    def __str__(self):
        return f'{self.employee_id} - {self.result} @ {self.decision_date}'


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
    # #9: phiếu đề xuất nâng level (PDF) sinh khi chốt lên level.
    proposal_pdf_url = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return f'{self.employee_id} → {self.target_position} ({self.target_level})'
