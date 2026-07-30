from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from cls_sync.models import ExamResult, ExamScoreAdjustment
from employees.models import Employee
from employees.services import best_exam_score, exam_pass


class ExamRegradeServiceTests(TestCase):
    """exam_pass/best_exam_score phai uu tien diem phuc khao (score_adjusted) hon diem CLS goc."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV-001', name='Nguyen Van A')

    def test_exam_pass_false_when_raw_score_below_threshold(self):
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('65.00'), passed=False,
        )
        self.assertFalse(exam_pass(self.employee, threshold=80))

    def test_exam_pass_true_after_regrade_raises_score_above_threshold(self):
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('65.00'), score_adjusted=Decimal('88.00'), passed=False,
        )
        self.assertTrue(exam_pass(self.employee, threshold=80))

    def test_best_exam_score_prefers_regraded_attempt(self):
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1, score=Decimal('90.00'),
        )
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=2,
            score=Decimal('40.00'), score_adjusted=Decimal('95.00'),
        )
        self.assertEqual(best_exam_score(self.employee), 95.0)


class ExamRegradeApiTests(TestCase):
    """API phuc khao diem thi: GET danh sach + POST sua diem, chi Admin/OM."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV-001', name='Nguyen Van A')
        self.exam = ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('65.00'), passed=False,
        )
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client = APIClient()

    def test_regrade_requires_admin_or_om_role(self):
        self.client.force_authenticate(self.trainer)
        url = reverse('employee-exam-regrade', args=[self.employee.id])
        resp = self.client.post(url, {'exam_result_id': self.exam.id, 'adjusted_score': 90, 'reason': 'Phuc khao'})
        self.assertEqual(resp.status_code, 403)

    def test_regrade_requires_reason(self):
        self.client.force_authenticate(self.admin)
        url = reverse('employee-exam-regrade', args=[self.employee.id])
        resp = self.client.post(url, {'exam_result_id': self.exam.id, 'adjusted_score': 90, 'reason': ''})
        self.assertEqual(resp.status_code, 400)

    def test_regrade_sets_score_adjusted_and_logs_audit(self):
        self.client.force_authenticate(self.admin)
        url = reverse('employee-exam-regrade', args=[self.employee.id])
        resp = self.client.post(
            url, {'exam_result_id': self.exam.id, 'adjusted_score': 90, 'reason': 'Phuc khao dot 1'},
        )
        self.assertEqual(resp.status_code, 200)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.score_adjusted, Decimal('90'))
        self.assertEqual(self.exam.score, Decimal('65.00'))  # diem goc khong doi
        self.assertEqual(resp.data['final_score'], Decimal('90'))
        self.assertIn('final_result', resp.data)

        adjustment = ExamScoreAdjustment.objects.get(exam_result=self.exam)
        self.assertEqual(adjustment.old_score, Decimal('65.00'))
        self.assertEqual(adjustment.new_score, Decimal('90'))
        self.assertEqual(adjustment.reason, 'Phuc khao dot 1')
        self.assertEqual(adjustment.adjusted_by, self.admin)

    def test_exam_results_list_returns_scores(self):
        self.client.force_authenticate(self.admin)
        url = reverse('employee-exam-results', args=[self.employee.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        row = resp.data[0]
        self.assertEqual(row['score'], Decimal('65.00'))
        self.assertIsNone(row['score_adjusted'])
        self.assertEqual(row['final_score'], Decimal('65.00'))
