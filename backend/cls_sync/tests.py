from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import Tenant
from cls_sync.models import CourseResult, ExamResult
from cls_sync.services import onboarding_eligible
from employees.models import Employee


class ExamResultFinalScoreTests(TestCase):
    """final_score phai uu tien score_adjusted (phuc khao) hon score (diem CLS goc)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV-001', name='Nguyen Van A')

    def test_final_score_falls_back_to_score_when_no_adjustment(self):
        exam = ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('65.00'), passed=False,
        )
        self.assertEqual(exam.final_score, Decimal('65.00'))

    def test_final_score_prefers_score_adjusted(self):
        exam = ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('65.00'), score_adjusted=Decimal('88.00'), passed=False,
        )
        self.assertEqual(exam.final_score, Decimal('88.00'))

    def test_sync_defaults_never_include_score_adjusted(self):
        """Mo phong dung defaults-dict cua sync_cls.py::sync_exams - update_or_create voi
        defaults KHONG co 'score_adjusted' phai giu nguyen diem phuc khao da co."""
        exam = ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('65.00'), score_adjusted=Decimal('88.00'), passed=False,
        )
        ExamResult.objects.update_or_create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            defaults={'score': Decimal('70.00'), 'passed': True, 'cls_id': 'abc', 'exam_full_name': '15N - Full'},
        )
        exam.refresh_from_db()
        self.assertEqual(exam.score, Decimal('70.00'))
        self.assertEqual(exam.score_adjusted, Decimal('88.00'))
        self.assertEqual(exam.final_score, Decimal('88.00'))


class OnboardingEligibleFallbackTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV-002', name='Nguyen Van B')

    def test_eligible_via_score_threshold(self):
        CourseResult.objects.create(
            tenant=self.tenant, employee=self.employee, course_name='Hội nhập cơ bản',
            score=Decimal('85.00'), status='Chưa đạt',
        )
        self.assertTrue(onboarding_eligible(self.employee, threshold=80))

    def test_not_eligible_when_no_course(self):
        self.assertFalse(onboarding_eligible(self.employee, threshold=80))

    def test_fallback_eligible_via_status_dat_when_score_below_threshold(self):
        CourseResult.objects.create(
            tenant=self.tenant, employee=self.employee, course_name='Hội nhập cơ bản',
            score=Decimal('0.00'), status='Đạt',
        )
        self.assertTrue(onboarding_eligible(self.employee, threshold=80))

    def test_fallback_eligible_via_progress_100_when_score_below_threshold(self):
        CourseResult.objects.create(
            tenant=self.tenant, employee=self.employee, course_name='Hội nhập cơ bản',
            score=Decimal('0.00'), status='Chưa đạt', progress=100,
        )
        self.assertTrue(onboarding_eligible(self.employee, threshold=80))

    def test_not_eligible_when_score_low_status_not_dat_progress_incomplete(self):
        CourseResult.objects.create(
            tenant=self.tenant, employee=self.employee, course_name='Hội nhập cơ bản',
            score=Decimal('30.00'), status='Chưa đạt', progress=40,
        )
        self.assertFalse(onboarding_eligible(self.employee, threshold=80))


class SyncClsRecomputeTests(TestCase):
    """Sau khi sync_cls dong bo xong, phai tinh lai final_result cho tung nhan su bi anh huong."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='Nguyen Van A')

    @override_settings(CLS_SECRET_KEY='test-key')
    @patch('employees.services.recompute_final_result')
    @patch('cls_sync.management.commands.sync_cls._get_json')
    def test_recompute_called_for_affected_employee_and_progress_persisted(self, mock_get_json, mock_recompute):
        def side_effect(base_url, path, params, stdout, style):
            if path == '/course/get-list':
                return [{'id': 1, 'code': 'HOINHAP_TEST', 'name': 'Hội nhập Test'}]
            if path == '/course/get-student-result':
                return [{'userCode': 'NV1', 'point': 0, 'progress': 100, 'isPassed': False, 'result': ''}]
            return []

        mock_get_json.side_effect = side_effect

        call_command('sync_cls', tenant='Demo Tenant')

        course = CourseResult.objects.get(employee=self.employee, course_name='Hội nhập Test')
        self.assertEqual(course.progress, 100)
        mock_recompute.assert_called_once_with(self.employee)
