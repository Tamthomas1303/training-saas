from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import Tenant, User
from cls_sync.models import CourseResult, ExamResult, ResultSource
from courses.models import Course, CourseModule, Enrollment, Lesson
from employees.models import Employee
from employees.services import exam_pass, lms_done
from exams.models import Assessment, Attempt

from .models import CertificateIssued, CertificateTemplate, CertProgram, XapiStatement
from .services import (
    check_and_issue_programs,
    issue_certificate,
    log_xapi,
    program_eligible,
    sync_result_to_profile,
)


def _make_enrollment(tenant, employee, sync_course_code='HOINHAP_X', status=Enrollment.Status.COMPLETED):
    course = Course.objects.create(tenant=tenant, title='Khóa demo', sync_course_code=sync_course_code)
    return Enrollment.objects.create(tenant=tenant, course=course, employee=employee, status=status)


def _make_attempt(tenant, employee, sync_exam_type='15N', passed=True, percent=Decimal('90.00'), attempt_no=1):
    assessment = Assessment.objects.create(tenant=tenant, title='Đề demo', sync_exam_type=sync_exam_type)
    return Attempt.objects.create(
        tenant=tenant, assessment=assessment, employee=employee, attempt_no=attempt_no,
        status=Attempt.Status.GRADED, passed=passed, percent=percent, score=Decimal('9.00'), max_score=Decimal('10.00'),
    )


class SyncCourseResultTests(TestCase):
    """Test A (phan khoa hoc): dong bo an toan CourseResult - khong dong CLS, idempotent, bo
    qua neu chua gan sync_course_code, va THAT SU goi lai recompute_final_result co san."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1')

    def test_skip_when_course_not_mapped(self):
        enrollment = _make_enrollment(self.tenant, self.employee, sync_course_code='')
        result = sync_result_to_profile(enrollment)
        self.assertIsNone(result)
        self.assertFalse(CourseResult.objects.filter(employee=self.employee).exists())

    def test_creates_internal_lms_course_result(self):
        enrollment = _make_enrollment(self.tenant, self.employee, sync_course_code='HOINHAP_X')
        result = sync_result_to_profile(enrollment)
        self.assertEqual(result.status, 'Đạt')
        self.assertEqual(result.source, ResultSource.INTERNAL_LMS)
        self.assertEqual(result.course_name, 'HOINHAP_X')

    def test_does_not_overwrite_existing_cls_row(self):
        CourseResult.objects.create(
            tenant=self.tenant, employee=self.employee, course_name='HOINHAP_X',
            status='Chưa đạt', source=ResultSource.CLS,
        )
        enrollment = _make_enrollment(self.tenant, self.employee, sync_course_code='HOINHAP_X')
        result = sync_result_to_profile(enrollment)
        result.refresh_from_db()
        self.assertEqual(result.source, ResultSource.CLS)
        self.assertEqual(result.status, 'Chưa đạt')  # KHONG bi ghi de thanh 'Đạt'
        self.assertEqual(CourseResult.objects.filter(employee=self.employee).count(), 1)

    def test_idempotent_running_twice(self):
        enrollment = _make_enrollment(self.tenant, self.employee, sync_course_code='HOINHAP_X')
        sync_result_to_profile(enrollment)
        sync_result_to_profile(enrollment)
        self.assertEqual(CourseResult.objects.filter(employee=self.employee).count(), 1)

    @patch('employees.services.recompute_final_result')
    def test_calls_recompute_final_result_not_reimplemented(self, mock_recompute):
        enrollment = _make_enrollment(self.tenant, self.employee, sync_course_code='HOINHAP_X')
        sync_result_to_profile(enrollment)
        mock_recompute.assert_called_once_with(self.employee)

    def test_end_to_end_flips_office_employee_to_pass(self):
        """Nhan vien Van phong (dieu kien PASS = lms_done + office_result='Đạt') - dong bo qua
        module Khoa hoc noi bo phai lam lms_done() thanh True va PASS THUC SU qua
        recompute_final_result KHONG SUA (chung minh an toan dau-cuoi, khong chi don vi)."""
        self.employee.operation_unit = Employee.OperationUnit.OFFICE
        self.employee.office_result = 'Đạt'
        self.employee.save()
        self.assertFalse(lms_done(self.employee))

        enrollment = _make_enrollment(self.tenant, self.employee, sync_course_code='HOINHAP_X')
        sync_result_to_profile(enrollment)

        self.assertTrue(lms_done(self.employee))
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.final_result, 'Pass thử việc')
        self.assertEqual(self.employee.pass_date, timezone.now().date())


class SyncExamResultTests(TestCase):
    """Test A (phan thi): tuong tu SyncCourseResultTests nhung cho ExamResult."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1')

    def test_skip_when_exam_not_mapped(self):
        attempt = _make_attempt(self.tenant, self.employee, sync_exam_type='')
        result = sync_result_to_profile(attempt)
        self.assertIsNone(result)
        self.assertFalse(ExamResult.objects.filter(employee=self.employee).exists())

    def test_creates_internal_lms_exam_result(self):
        attempt = _make_attempt(self.tenant, self.employee, sync_exam_type='15N', percent=Decimal('92.00'))
        result = sync_result_to_profile(attempt)
        self.assertEqual(result.source, ResultSource.INTERNAL_LMS)
        self.assertEqual(result.exam_name, '15N')
        self.assertEqual(result.score, Decimal('92.00'))
        self.assertTrue(result.passed)

    def test_does_not_overwrite_existing_cls_row(self):
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('60.00'), source=ResultSource.CLS,
        )
        attempt = _make_attempt(self.tenant, self.employee, sync_exam_type='15N', attempt_no=1)
        result = sync_result_to_profile(attempt)
        result.refresh_from_db()
        self.assertEqual(result.source, ResultSource.CLS)
        self.assertEqual(result.score, Decimal('60.00'))
        self.assertEqual(ExamResult.objects.filter(employee=self.employee).count(), 1)

    def test_idempotent_running_twice(self):
        attempt = _make_attempt(self.tenant, self.employee, sync_exam_type='15N')
        sync_result_to_profile(attempt)
        sync_result_to_profile(attempt)
        self.assertEqual(ExamResult.objects.filter(employee=self.employee).count(), 1)

    def test_makes_exam_pass_true_via_real_unmodified_logic(self):
        self.assertFalse(exam_pass(self.employee))
        attempt = _make_attempt(self.tenant, self.employee, sync_exam_type='15N', percent=Decimal('85.00'))
        sync_result_to_profile(attempt)
        self.assertTrue(exam_pass(self.employee))


class LogXapiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1')

    def test_creates_statement(self):
        log_xapi(self.employee, 'viewed', 'lesson', 42, result_json={'foo': 'bar'})
        stmt = XapiStatement.objects.get(employee=self.employee)
        self.assertEqual(stmt.verb, 'viewed')
        self.assertEqual(stmt.object_type, 'lesson')
        self.assertEqual(stmt.object_id, 42)
        self.assertEqual(stmt.result_json, {'foo': 'bar'})

    def test_never_raises_on_failure(self):
        """object_id la IntegerField khong null - truyen None se gay IntegrityError o DB, nhung
        log_xapi PHAI tu nuot loi (khong duoc lam hong luong hoc/thi chinh)."""
        try:
            log_xapi(self.employee, 'viewed', 'lesson', None)
        except Exception as exc:  # noqa: BLE001
            self.fail(f'log_xapi không được raise ra ngoài, nhưng đã raise {exc!r}')


class ProgramEligibleTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1')

    def test_positions_count(self):
        from employees.models import LevelUpEnrollment

        program = CertProgram.objects.create(
            tenant=self.tenant, name='Chuyên môn', type=CertProgram.Type.CHUYEN_MON,
            rule_config={'kind': 'positions_count', 'count': 3},
        )
        self.employee.position = 'Phục vụ'
        self.employee.save()
        ok, detail = program_eligible(self.employee, program)
        self.assertFalse(ok)
        self.assertEqual(detail['positions_count'], 1)

        LevelUpEnrollment.objects.create(
            tenant=self.tenant, employee=self.employee, target_position='Thu ngân', status='completed',
        )
        LevelUpEnrollment.objects.create(
            tenant=self.tenant, employee=self.employee, target_position='Pha chế', status='completed',
        )
        ok, detail = program_eligible(self.employee, program)
        self.assertTrue(ok)
        self.assertEqual(detail['positions_count'], 3)

    def test_course_exam(self):
        program = CertProgram.objects.create(
            tenant=self.tenant, name='Train the trainer', type=CertProgram.Type.BQL,
            rule_config={'kind': 'course_exam', 'course': 'TTT_COURSE', 'exam': 'TTT_EXAM'},
        )
        ok, detail = program_eligible(self.employee, program)
        self.assertFalse(ok)
        self.assertFalse(detail['course_ok'])
        self.assertFalse(detail['exam_ok'])

        CourseResult.objects.create(
            tenant=self.tenant, employee=self.employee, course_name='TTT_COURSE', status='Đạt',
        )
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='TTT_EXAM', attempt=1, score=Decimal('90'),
        )
        ok, detail = program_eligible(self.employee, program)
        self.assertTrue(ok)

    def test_bql_position_ignores_pending_evaluation_items(self):
        program = CertProgram.objects.create(
            tenant=self.tenant, name='Giám sát', type=CertProgram.Type.BQL,
            rule_config={
                'kind': 'bql_position',
                'require': ['training', 'final_exam', 'council', 'shift_eval', 'interview'],
            },
        )
        ok, detail = program_eligible(self.employee, program)
        self.assertFalse(ok)  # chua co training/final_exam
        self.assertEqual(detail['council'], 'pending')
        self.assertEqual(detail['shift_eval'], 'pending')
        self.assertEqual(detail['interview'], 'pending')

        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='BQL_EXAM', attempt=1, score=Decimal('90'),
        )
        # checklist_progress_percent se tra 0 vi khong co restaurant/checklist - gia lap qua patch
        # (program_eligible import ham nay CUC BO tu employees.services, nen phai patch dung
        # module goc de lan import lai luc goi ham lay duoc ban gia lap).
        with patch('employees.services.checklist_progress_percent', return_value=100):
            ok, detail = program_eligible(self.employee, program)
        self.assertTrue(ok)
        self.assertTrue(detail['training'])
        self.assertTrue(detail['final_exam'])
        # cac muc cho tich hop van 'pending', KHONG chan cap chung chi (dung y prompt)
        self.assertEqual(detail['council'], 'pending')


class IssueCertificateTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='Nguyễn Văn A')
        self.template = CertificateTemplate.objects.create(
            tenant=self.tenant, type=CertificateTemplate.Type.HOC, name='Mẫu khóa học',
        )

    @patch('integration.services.upload_pdf_bytes', return_value='https://pub-x.r2.dev/certificates/x.pdf')
    def test_issue_certificate_creates_record(self, mock_upload):
        cert = issue_certificate(
            self.employee, self.template, ref_type='course', ref_id=1,
            program_or_course_name='Khóa demo', completion_line='ĐÃ HOÀN THÀNH KHOÁ HỌC',
        )
        self.assertTrue(cert.code)
        self.assertEqual(cert.issue_date, timezone.now().date())
        self.assertEqual(cert.pdf_url, 'https://pub-x.r2.dev/certificates/x.pdf')
        mock_upload.assert_called_once()

    @patch('integration.services.upload_pdf_bytes', return_value='https://pub-x.r2.dev/certificates/x.pdf')
    def test_issue_certificate_not_duplicated(self, mock_upload):
        first = issue_certificate(self.employee, self.template, ref_type='course', ref_id=1)
        second = issue_certificate(self.employee, self.template, ref_type='course', ref_id=1)
        self.assertEqual(first.id, second.id)
        self.assertEqual(CertificateIssued.objects.filter(employee=self.employee).count(), 1)
        mock_upload.assert_called_once()  # KHONG sinh PDF lai lan 2

    @patch('integration.services.upload_pdf_bytes', return_value='https://pub-x.r2.dev/certificates/x.pdf')
    def test_check_and_issue_programs(self, mock_upload):
        program = CertProgram.objects.create(
            tenant=self.tenant, name='Chuyên môn', type=CertProgram.Type.CHUYEN_MON,
            rule_config={'kind': 'positions_count', 'count': 1}, certificate_template=self.template,
        )
        self.employee.position = 'Phục vụ'
        self.employee.save()

        issued = check_and_issue_programs(self.employee)
        self.assertEqual(len(issued), 1)
        self.assertEqual(issued[0].ref_type, CertificateIssued.RefType.PROGRAM)
        self.assertEqual(issued[0].program_id, program.id)

        # goi lai lan 2 - khong cap trung
        issued_again = check_and_issue_programs(self.employee)
        self.assertEqual(len(issued_again), 1)
        self.assertEqual(issued_again[0].id, issued[0].id)
        self.assertEqual(CertificateIssued.objects.filter(employee=self.employee).count(), 1)

    def test_check_and_issue_programs_skips_without_template(self):
        CertProgram.objects.create(
            tenant=self.tenant, name='Chuyên môn', type=CertProgram.Type.CHUYEN_MON,
            rule_config={'kind': 'positions_count', 'count': 1}, certificate_template=None,
        )
        self.employee.position = 'Phục vụ'
        self.employee.save()
        issued = check_and_issue_programs(self.employee)
        self.assertEqual(issued, [])
