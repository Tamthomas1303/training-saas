from decimal import Decimal

from django.test import TestCase

from accounts.models import Tenant
from cls_sync.models import ExamResult
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
