"""
Module "noi he thong" - MVP Dot 3/3 (Module_KhoaHoc_KyThi_Spec_v0.3.md). Noi 2 app moi
(courses, exams) vao he thong dang chay: dong bo ket qua ve ho so (xem services.py, KHONG dung
model o day, ghi thang vao cls_sync.CourseResult/ExamResult), hoan thanh offline co nguoi xac
nhan, log xAPI, nen chung chi.

OfflineConfirmation/XapiStatement dung "target_type/target_id" (khong FK truc tiep vao
courses.Lesson/Course/exams.Assessment) de app nay KHONG can import model cua courses/exams -
tranh vong lap import (courses/exams goi services o day, o day khong duoc goi nguoc lai
courses.models/exams.models tu module nay, chi tu services.py).
"""
from django.db import models

from accounts.models import Tenant, User
from employees.models import Employee


class OfflineConfirmation(models.Model):
    """Audit 1 lan xac nhan hoan thanh HO (khong qua player) - Dot 3 phan B. Batbuoc luu lai AI
    xac nhan + KHI NAO + HINH THUC gi, hien nhan 'Hoan thanh offline (xac nhan boi X - ngay)'
    o tien do (xem courses.services.confirm_offline_completion)."""

    class TargetType(models.TextChoices):
        LESSON = 'lesson', 'Bài học'
        COURSE = 'course', 'Toàn bộ khóa học'

    class Method(models.TextChoices):
        KEM_TAI_CHO = 'kem_tai_cho', 'Kèm tại chỗ'
        VIDEO_NHOM = 'video_nhom', 'Học nhóm qua video'
        CHECKLIST_GIAY = 'checklist_giay', 'Checklist giấy'
        KHAC = 'khac', 'Khác'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='offline_confirmations')
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.IntegerField()
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='offline_confirmations')
    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name='offline_confirmations_made', null=True, blank=True,
    )
    confirmed_at = models.DateTimeField(auto_now_add=True)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.KEM_TAI_CHO)
    note = models.TextField(blank=True)
    evidence_url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ['-confirmed_at']

    def __str__(self):
        return f'{self.employee_id} - {self.target_type}:{self.target_id}'


class XapiStatement(models.Model):
    """Log su kien hoc/thi kieu xAPI (actor-verb-object) - Dot 3 phan C. MVP luu NOI BO (chua
    day ra LRS ngoai - P2). Khong FK cung truc tiep vao courses/exams (xem docstring dau file)."""

    class Verb(models.TextChoices):
        VIEWED = 'viewed', 'Đã xem'
        STARTED = 'started', 'Đã bắt đầu'
        COMPLETED = 'completed', 'Đã hoàn thành'
        PASSED = 'passed', 'Đạt'
        FAILED = 'failed', 'Không đạt'
        CONFIRMED_OFFLINE = 'confirmed_offline', 'Xác nhận offline'

    class ObjectType(models.TextChoices):
        LESSON = 'lesson', 'Bài học'
        COURSE = 'course', 'Khóa học'
        ASSESSMENT = 'assessment', 'Đề thi'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='xapi_statements')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='xapi_statements')
    verb = models.CharField(max_length=20, choices=Verb.choices)
    object_type = models.CharField(max_length=20, choices=ObjectType.choices)
    object_id = models.IntegerField()
    # {score, percent, passed} - tuy moc, co the rong.
    result_json = models.JSONField(null=True, blank=True)
    context_json = models.JSONField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.employee_id} {self.verb} {self.object_type}:{self.object_id}'


DEFAULT_CERT_FIELDS_CONFIG = {
    # Toa do MAC DINH tren khung ngang 853x603pt (goc duoi-trai la 0,0 theo he PDF) - CHI la gia
    # tri khoi dong hop ly de dung duoc ngay; anh Chung CAN CAN CHINH LAI sau khi upload mau that
    # (xem prompt Dot 3 - "cau hinh tay"). Sua qua CertificateTemplate.fields_config, khong can
    # sua code.
    'recipient_name': {'x': 426, 'y': 330, 'font_size': 26, 'bold': True, 'align': 'center'},
    'program_or_course_name': {'x': 426, 'y': 280, 'font_size': 20, 'bold': True, 'align': 'center'},
    'completion_line': {'x': 426, 'y': 250, 'font_size': 13, 'bold': False, 'align': 'center'},
    'issue_date': {'x': 690, 'y': 55, 'font_size': 10, 'bold': False, 'align': 'left'},
    'cert_code': {'x': 690, 'y': 40, 'font_size': 10, 'bold': False, 'align': 'left'},
}


class CertificateTemplate(models.Model):
    """Mau chung chi (anh nen do admin upload + toa do tung o chu). Dot 3 phan D."""

    class Type(models.TextChoices):
        HOC = 'hoc', 'Chứng chỉ khóa học'
        THI = 'thi', 'Chứng chỉ bài thi'
        CHUONG_TRINH = 'chuong_trinh', 'Chứng chỉ chương trình'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='certificate_templates')
    type = models.CharField(max_length=20, choices=Type.choices)
    name = models.CharField(max_length=255)
    template_pdf_url = models.URLField(max_length=500, blank=True)
    fields_config = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.fields_config:
            self.fields_config = dict(DEFAULT_CERT_FIELDS_CONFIG)
        super().save(*args, **kwargs)


class CertProgram(models.Model):
    """Chuong trinh chung chi (dieu kien gop nhieu khoa/thi/vi tri) - Dot 3 phan D. Ten
    'CertProgram' (khong phai 'Program') de tranh dam voi sourcing.Program (chuong trinh dao
    tao nguon/cap trung, khac muc dich - da co san tu truoc).

    rule_config (JSON, cau hinh duoc, xem integration.services.program_eligible):
      - chuyen mon: {"kind": "positions_count", "count": 3}
      - BQL train-the-trainer: {"kind": "course_exam", "course": "<sync_course_code>",
        "exam": "<sync_exam_type>"}
      - BQL theo vi tri: {"kind": "bql_position", "require": ["training", "final_exam",
        "council", "shift_eval", "interview"]} - MVP CHI kiem training + final_exam; cac muc
        council/shift_eval/interview de co (khong chan) cho tich hop evaluation o P2.
    """

    class Type(models.TextChoices):
        CHUYEN_MON = 'chuyen_mon', 'Đào tạo kỹ năng nghề'
        BQL = 'bql', 'Ban quản lý'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='cert_programs')
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=Type.choices)
    rule_config = models.JSONField(default=dict, blank=True)
    certificate_template = models.ForeignKey(
        CertificateTemplate, on_delete=models.SET_NULL, related_name='cert_programs', null=True, blank=True,
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class CertificateIssued(models.Model):
    """1 chung chi da cap cho 1 nhan su. unique (employee, ref_type, ref_id) -> KHONG cap trung
    (goi issue_certificate() nhieu lan cho cung ref van tra ve ban ghi cu, khong tao moi)."""

    class RefType(models.TextChoices):
        COURSE = 'course', 'Khóa học'
        ASSESSMENT = 'assessment', 'Đề thi'
        PROGRAM = 'program', 'Chương trình'

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='certificates_issued')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='certificates')
    template = models.ForeignKey(CertificateTemplate, on_delete=models.PROTECT, related_name='issued')
    program = models.ForeignKey(
        CertProgram, on_delete=models.SET_NULL, related_name='certificates_issued', null=True, blank=True,
    )
    ref_type = models.CharField(max_length=20, choices=RefType.choices)
    ref_id = models.IntegerField()
    issue_date = models.DateField()
    code = models.CharField(max_length=50, unique=True)
    pdf_url = models.URLField(max_length=500, blank=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'ref_type', 'ref_id')
        ordering = ['-issued_at']

    def __str__(self):
        return f'{self.code} - {self.employee_id}'
