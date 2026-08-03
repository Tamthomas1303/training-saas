import datetime
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from checklist.models import Checklist, TrainingProgress
from cls_sync.models import ExamResult, ExamScoreAdjustment
from employees.dashboard import _month_end, _s_pass_rate_this_month
from employees.models import Employee
from employees.services import best_exam_score, change_employee_status, emp_type, exam_pass, recompute_final_result
from employees.management.commands.import_july_data import (
    Command as ImportJulyDataCommand,
)
from employees.management.commands.import_july_data import (
    _match_evidence_filename,
    _match_training_record_filename,
    _parse_decimal_comma,
    _parse_sheet_date,
    _parse_skill_percent,
    _parse_skill_result,
    build_checklist_code_map,
)
from evaluation.models import Council, CouncilMember, Evaluation, EvaluationDetail
from restaurants.models import Restaurant
from sourcing.models import Notification


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


class EmpTypeTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_derives_from_job_level_first_letter(self):
        e = Employee.objects.create(tenant=self.tenant, code='NV1', name='A', job_level='S2')
        self.assertEqual(emp_type(e), 'S')
        e.job_level = 'P1'
        self.assertEqual(emp_type(e), 'P')
        e.job_level = 'O1'
        self.assertEqual(emp_type(e), 'O')

    def test_blank_when_unknown(self):
        e = Employee.objects.create(tenant=self.tenant, code='NV2', name='B', job_level='')
        self.assertEqual(emp_type(e), '')
        e.job_level = 'X9'
        self.assertEqual(emp_type(e), '')


class EmployeeListApiTests(TestCase):
    """emp_type/days_left o serializer + quick_filter tren EmployeeViewSet.list."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.today = datetime.date.today()

    def test_emp_type_and_days_left_in_response(self):
        Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', job_level='S1',
            start_date=self.today - datetime.timedelta(days=3), probation_days=15,
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        resp = self.client.get('/api/employees/')
        row = resp.data['results'][0]
        self.assertEqual(row['emp_type'], 'S')
        self.assertEqual(row['days_left'], 12)  # 15 - 3

    def test_quick_filter_no_training(self):
        with_progress = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='Co tien do', restaurant=self.restaurant,
            position='Phục vụ', job_level='S1', employee_status=Employee.EmployeeStatus.PROBATION,
        )
        without_progress = Employee.objects.create(
            tenant=self.tenant, code='NV2', name='Chua dao tao', restaurant=self.restaurant,
            position='Phục vụ', job_level='S1', employee_status=Employee.EmployeeStatus.PROBATION,
        )
        checklist = Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='phục vụ', task_name='Buoi 1',
        )
        TrainingProgress.objects.create(
            tenant=self.tenant, employee=with_progress, checklist=checklist,
            status=TrainingProgress.Status.DONE,
        )
        resp = self.client.get('/api/employees/', {'quick_filter': 'no_training'})
        ids = {row['id'] for row in resp.data['results']}
        self.assertIn(without_progress.id, ids)
        self.assertNotIn(with_progress.id, ids)

    def test_quick_filter_s_deadline_soon_and_overdue(self):
        soon = Employee.objects.create(
            tenant=self.tenant, code='NV3', name='Sap den han', job_level='S1',
            start_date=self.today - datetime.timedelta(days=13), probation_days=15,
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        overdue = Employee.objects.create(
            tenant=self.tenant, code='NV4', name='Qua han', job_level='S1',
            start_date=self.today - datetime.timedelta(days=20), probation_days=15,
            employee_status=Employee.EmployeeStatus.PROBATION, final_result='Tiếp tục thử việc',
        )
        not_yet = Employee.objects.create(
            tenant=self.tenant, code='NV5', name='Con som', job_level='S1',
            start_date=self.today - datetime.timedelta(days=1), probation_days=15,
            employee_status=Employee.EmployeeStatus.PROBATION,
        )

        resp_soon = self.client.get('/api/employees/', {'quick_filter': 's_deadline_soon'})
        soon_ids = {row['id'] for row in resp_soon.data['results']}
        self.assertIn(soon.id, soon_ids)
        self.assertNotIn(overdue.id, soon_ids)
        self.assertNotIn(not_yet.id, soon_ids)

        resp_overdue = self.client.get('/api/employees/', {'quick_filter': 's_overdue'})
        overdue_ids = {row['id'] for row in resp_overdue.data['results']}
        self.assertIn(overdue.id, overdue_ids)
        self.assertNotIn(soon.id, overdue_ids)
        self.assertNotIn(not_yet.id, overdue_ids)


class AlertNoTrainingCommandTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.trainer = User.objects.create_user(
            username='trainer1', password='x', tenant=self.tenant, role='trainer',
            restaurant=self.restaurant, email='trainer1@example.com',
        )
        self.today = datetime.date.today()

    def _make_employee(self, code, days_since_start, **kwargs):
        return Employee.objects.create(
            tenant=self.tenant, code=code, name=f'NV {code}', restaurant=self.restaurant,
            position='Phục vụ', start_date=self.today - datetime.timedelta(days=days_since_start),
            employee_status=Employee.EmployeeStatus.PROBATION, **kwargs,
        )

    def test_alerts_employee_within_range_with_zero_progress(self):
        self._make_employee('NV1', 10)
        call_command('alert_no_training', tenant='Demo Tenant')

        self.assertEqual(Notification.objects.filter(category='no_training').count(), 1)
        notification = Notification.objects.get(category='no_training')
        self.assertEqual(notification.user, self.trainer)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['trainer1@example.com'])

    def test_skips_outside_day_range(self):
        self._make_employee('NV2', 3)   # < 5 ngay
        self._make_employee('NV3', 40)  # > 30 ngay
        call_command('alert_no_training', tenant='Demo Tenant')
        self.assertEqual(Notification.objects.filter(category='no_training').count(), 0)

    def test_skips_when_already_has_progress(self):
        employee = self._make_employee('NV4', 10)
        checklist = Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='phục vụ', task_name='Buoi 1',
        )
        TrainingProgress.objects.create(
            tenant=self.tenant, employee=employee, checklist=checklist,
            status=TrainingProgress.Status.DONE,
        )
        call_command('alert_no_training', tenant='Demo Tenant')
        self.assertEqual(Notification.objects.filter(category='no_training').count(), 0)

    def test_dedup_only_once_per_employee(self):
        self._make_employee('NV5', 10)
        call_command('alert_no_training', tenant='Demo Tenant')
        call_command('alert_no_training', tenant='Demo Tenant')
        self.assertEqual(Notification.objects.filter(category='no_training').count(), 1)
        self.assertEqual(len(mail.outbox), 1)


class RecomputeFinalResultApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A',
            operation_unit=Employee.OperationUnit.PRODUCTION,  # luon Pass thu viec - de kiem tra don gian
            final_result='',
        )
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client = APIClient()

    def test_requires_admin_or_om_role(self):
        self.client.force_authenticate(self.trainer)
        url = reverse('employee-recompute-final', args=[self.employee.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_recomputes_and_returns_updated_employee(self):
        self.client.force_authenticate(self.admin)
        url = reverse('employee-recompute-final', args=[self.employee.id])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['final_result'], 'Pass thử việc')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.final_result, 'Pass thử việc')


class SPassRateThisMonthTests(TestCase):
    """Ty le dat thu viec cap S trong thang (employees/dashboard.py::_s_pass_rate_this_month)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.today = datetime.date(2026, 7, 31)  # thang 31 ngay, de test dung bien "roi mung 1"

    def _emp(self, code, job_level, start_date, status=Employee.EmployeeStatus.PROBATION, final_result=''):
        return Employee.objects.create(
            tenant=self.tenant, code=code, name=f'NV {code}', job_level=job_level,
            start_date=start_date, employee_status=status, final_result=final_result,
        )

    def test_full_breakdown(self):
        passed = self._emp('S1', 'S1', datetime.date(2026, 7, 5), final_result='Pass thử việc')
        self._emp('P1', 'P1', datetime.date(2026, 7, 5))  # khong phai cap S -> loai
        self._emp('S2', 'S2', datetime.date(2026, 7, 20), status=Employee.EmployeeStatus.RESIGNED)
        self._emp('S3', 'S3', datetime.date(2026, 7, 20))  # han danh gia roi thang sau (8/4)
        self._emp('S4', 'S4', datetime.date(2026, 7, 16), final_result='Tiếp tục thử việc')  # han 7/31 - van tinh thang nay
        self._emp('S5', 'S5', datetime.date(2026, 6, 25))  # vao thang truoc -> loai

        employees = list(Employee.objects.filter(tenant=self.tenant))
        result = _s_pass_rate_this_month(employees, self.today)

        self.assertEqual(result['joined'], 4)     # S1, S2, S3, S4
        self.assertEqual(result['resigned'], 1)   # S2
        self.assertEqual(result['eval_next'], 1)  # S3 (han 8/4 > 7/31)
        self.assertEqual(result['num'], 1)         # chi S1 da Pass
        self.assertEqual(result['den'], 2)         # 4 - 1 - 1
        self.assertEqual(result['rate'], 50)
        self.assertTrue(Employee.objects.filter(pk=passed.pk, final_result='Pass thử việc').exists())

    def test_deadline_falling_exactly_on_month_end_still_counts_this_month(self):
        self._emp('S1', 'S1', datetime.date(2026, 7, 16))  # 16 + 15 = 31 (<=cuoi thang)
        employees = list(Employee.objects.filter(tenant=self.tenant))
        result = _s_pass_rate_this_month(employees, self.today)
        self.assertEqual(result['eval_next'], 0)
        self.assertEqual(result['den'], 1)

    def test_rate_zero_when_denominator_not_positive(self):
        self._emp('S1', 'S1', datetime.date(2026, 7, 20), status=Employee.EmployeeStatus.RESIGNED)
        employees = list(Employee.objects.filter(tenant=self.tenant))
        result = _s_pass_rate_this_month(employees, self.today)
        self.assertEqual(result['den'], 0)
        self.assertEqual(result['rate'], 0)


class DashboardStatsApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_dashboard_includes_s_pass_rate_breakdown(self):
        # Khong gia dinh vi tri "an toan" trong thang (vd start_date=hom nay co the roi han
        # danh gia sang thang sau neu chay vao cuoi thang) - tinh ky vong bang dung logic
        # _month_end de test on dinh bat ke chay ngay nao trong thang.
        today = timezone.now().date()
        deadline = today + datetime.timedelta(days=15)
        expected_eval_next = 1 if deadline > _month_end(today) else 0
        expected_den = 1 - expected_eval_next
        expected_rate = round(1 / expected_den * 100) if expected_den > 0 else 0

        Employee.objects.create(
            tenant=self.tenant, code='S1', name='A', job_level='S1', start_date=today,
            final_result='Pass thử việc',
        )
        resp = self.client.get('/api/employees/dashboard/')
        self.assertEqual(resp.status_code, 200)
        stats = resp.data['stats']
        self.assertEqual(stats['num'], 1)
        self.assertEqual(stats['joined'], 1)
        self.assertEqual(stats['resigned'], 0)
        self.assertEqual(stats['eval_next'], expected_eval_next)
        self.assertEqual(stats['den'], expected_den)
        self.assertEqual(stats['pass_rate'], expected_rate)


class RecomputeFinalResultNoBackfillTests(TestCase):
    """pass_date CHI duoc set khi final_result THAT SU chuyen sang Pass, khong backfill cho
    nguoi da Pass tu truoc (loi cu: chi kiem tra pass_date dang trong, khong kiem final_result
    CU)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_stamps_pass_date_on_genuine_transition(self):
        e = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A',
            operation_unit=Employee.OperationUnit.PRODUCTION, final_result='',
        )
        recompute_final_result(e)
        self.assertEqual(e.final_result, 'Pass thử việc')
        self.assertEqual(e.pass_date, datetime.date.today())

    def test_does_not_backfill_pass_date_for_already_pass_employee(self):
        e = Employee.objects.create(
            tenant=self.tenant, code='NV2', name='B',
            operation_unit=Employee.OperationUnit.PRODUCTION, final_result='Pass thử việc',
            pass_date=None,
        )
        recompute_final_result(e)
        self.assertEqual(e.final_result, 'Pass thử việc')
        self.assertIsNone(e.pass_date)  # KHONG backfill hom nay

    def test_clears_pass_date_when_leaving_pass(self):
        e = Employee.objects.create(
            tenant=self.tenant, code='NV3', name='C',
            final_result='Pass thử việc', pass_date=datetime.date(2026, 1, 1),
        )
        recompute_final_result(e)  # operation_unit rong -> roi vao nhanh "Tiep tuc thu viec"
        self.assertNotEqual(e.final_result, 'Pass thử việc')
        self.assertIsNone(e.pass_date)


class ChangeEmployeeStatusResignedAtTests(TestCase):
    """resigned_at CHI duoc set khi employee_status THAT SU chuyen sang resigned - cung 1 loi
    (va cach sua) nhu pass_date."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_stamps_resigned_at_on_transition(self):
        e = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', employee_status=Employee.EmployeeStatus.PROBATION,
        )
        change_employee_status(e, 'resigned')
        self.assertEqual(e.resigned_at, datetime.date.today())

    def test_does_not_backfill_resigned_at_when_already_resigned(self):
        e = Employee.objects.create(
            tenant=self.tenant, code='NV2', name='B',
            employee_status=Employee.EmployeeStatus.RESIGNED, resigned_at=None,
        )
        change_employee_status(e, 'resigned')
        self.assertIsNone(e.resigned_at)

    def test_clears_resigned_at_when_leaving_resigned(self):
        e = Employee.objects.create(
            tenant=self.tenant, code='NV3', name='C',
            employee_status=Employee.EmployeeStatus.RESIGNED, resigned_at=datetime.date(2026, 1, 1),
        )
        change_employee_status(e, 'active')
        self.assertIsNone(e.resigned_at)


class ClearBackfilledPassDateCommandTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_clears_pass_date_for_currently_pass_employees_only(self):
        passed_with_date = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', final_result='Pass thử việc',
            pass_date=datetime.date(2026, 1, 1),
        )
        not_passed = Employee.objects.create(
            tenant=self.tenant, code='NV2', name='B', final_result='Tiếp tục thử việc',
            pass_date=datetime.date(2026, 1, 1),
        )
        call_command('clear_backfilled_pass_date', tenant='Demo Tenant')

        passed_with_date.refresh_from_db()
        not_passed.refresh_from_db()
        self.assertIsNone(passed_with_date.pass_date)
        self.assertEqual(not_passed.pass_date, datetime.date(2026, 1, 1))  # khong dung -> khong dong

    def test_idempotent_second_run_does_nothing(self):
        Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', final_result='Pass thử việc',
            pass_date=datetime.date(2026, 1, 1),
        )
        call_command('clear_backfilled_pass_date', tenant='Demo Tenant')
        call_command('clear_backfilled_pass_date', tenant='Demo Tenant')  # khong loi


class ClearTestDataCommandTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', trainer=self.trainer,
            probation_result_pdf_url='https://pub-x.r2.dev/ketquathuviec/1/x.pdf',
            pass_date=datetime.date(2026, 1, 1), final_result='Pass thử việc',
            commission_status='eligible', retrain_deadline=datetime.date(2026, 2, 1),
        )
        checklist = Checklist.objects.create(tenant=self.tenant, task_name='B1')
        self.progress = TrainingProgress.objects.create(
            tenant=self.tenant, employee=self.employee, checklist=checklist, trainer=self.trainer,
            img_tailieu='https://pub-x.r2.dev/evidence/1/a.jpg', pdf_url='https://pub-x.r2.dev/bienban/1/b.pdf',
        )
        self.evaluation = Evaluation.objects.create(
            tenant=self.tenant, employee=self.employee, evaluator=self.trainer, eval_type='Skill_BQL',
            pdf_url='https://pub-x.r2.dev/danhgia/1/c.pdf',
        )
        EvaluationDetail.objects.create(
            tenant=self.tenant, evaluation=self.evaluation, criteria_id='1', content='X',
            photo_url='https://pub-x.r2.dev/danhgia/1/d.jpg',
        )
        self.council = Council.objects.create(tenant=self.tenant, employee=self.employee, kind='skill')
        CouncilMember.objects.create(tenant=self.tenant, council=self.council, user=self.trainer)

    @patch('employees.management.commands.clear_test_data.delete_by_url')
    def test_dry_run_deletes_nothing(self, mock_delete):
        call_command('clear_test_data', tenant='Demo Tenant', dry_run=True)

        mock_delete.assert_not_called()
        self.assertEqual(TrainingProgress.objects.count(), 1)
        self.assertEqual(Evaluation.objects.count(), 1)
        self.assertEqual(EvaluationDetail.objects.count(), 1)
        self.assertEqual(Council.objects.count(), 1)
        self.assertEqual(CouncilMember.objects.count(), 1)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.probation_result_pdf_url)
        self.assertIsNotNone(self.employee.pass_date)

    @patch('employees.management.commands.clear_test_data.delete_by_url')
    def test_no_flags_defaults_to_dry_run(self, mock_delete):
        call_command('clear_test_data', tenant='Demo Tenant')

        mock_delete.assert_not_called()
        self.assertEqual(TrainingProgress.objects.count(), 1)

    @patch('employees.management.commands.clear_test_data.delete_by_url')
    def test_confirm_deletes_records_and_files_and_resets_employee(self, mock_delete):
        call_command('clear_test_data', tenant='Demo Tenant', confirm=True)

        self.assertEqual(TrainingProgress.objects.count(), 0)
        self.assertEqual(Evaluation.objects.count(), 0)
        self.assertEqual(EvaluationDetail.objects.count(), 0)
        self.assertEqual(Council.objects.count(), 0)
        self.assertEqual(CouncilMember.objects.count(), 0)

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.probation_result_pdf_url, '')
        self.assertIsNone(self.employee.pass_date)
        self.assertEqual(self.employee.final_result, '')
        self.assertEqual(self.employee.commission_status, '')
        self.assertIsNone(self.employee.retrain_deadline)

        deleted_urls = {c.args[0] for c in mock_delete.call_args_list}
        self.assertIn('https://pub-x.r2.dev/evidence/1/a.jpg', deleted_urls)
        self.assertIn('https://pub-x.r2.dev/bienban/1/b.pdf', deleted_urls)
        self.assertIn('https://pub-x.r2.dev/danhgia/1/c.pdf', deleted_urls)
        self.assertIn('https://pub-x.r2.dev/danhgia/1/d.jpg', deleted_urls)
        self.assertIn('https://pub-x.r2.dev/ketquathuviec/1/x.pdf', deleted_urls)

    def test_dry_run_and_confirm_together_raises(self):
        with self.assertRaises(CommandError):
            call_command('clear_test_data', tenant='Demo Tenant', dry_run=True, confirm=True)

    @patch('employees.management.commands.clear_test_data.delete_by_url')
    def test_confirm_does_not_reset_legacy_employee(self, mock_delete):
        legacy = Employee.objects.create(
            tenant=self.tenant, code='NV_LEGACY', name='Legacy', is_legacy=True,
            probation_result_pdf_url='https://pub-x.r2.dev/ketquathuviec/1/legacy.pdf',
            pass_date=datetime.date(2020, 1, 1), final_result='Pass thử việc',
        )

        call_command('clear_test_data', tenant='Demo Tenant', confirm=True)

        legacy.refresh_from_db()
        self.assertEqual(legacy.probation_result_pdf_url, 'https://pub-x.r2.dev/ketquathuviec/1/legacy.pdf')
        self.assertEqual(legacy.pass_date, datetime.date(2020, 1, 1))
        self.assertEqual(legacy.final_result, 'Pass thử việc')
        deleted_urls = {c.args[0] for c in mock_delete.call_args_list}
        self.assertNotIn('https://pub-x.r2.dev/ketquathuviec/1/legacy.pdf', deleted_urls)


class ImportJulyDataHelperTests(TestCase):
    def test_match_evidence_filename_parses_kind_code_timestamp_ext(self):
        result = _match_evidence_filename('tailieu_CL-000005_1784521654444.jpg')
        self.assertEqual(result, ('tailieu', 'CL-000005', 1784521654444, 'jpg'))

    def test_match_evidence_filename_case_insensitive(self):
        result = _match_evidence_filename('HuongDan_CL-000005_123.JPG')
        self.assertEqual(result, ('huongdan', 'CL-000005', 123, 'jpg'))

    def test_match_evidence_filename_rejects_unrelated_name(self):
        self.assertIsNone(_match_evidence_filename('random_photo.jpg'))
        self.assertIsNone(_match_evidence_filename('tailieu_CL-000005.jpg'))

    def test_match_training_record_filename(self):
        result = _match_training_record_filename('BienBanDaoTao_AM002868_CL-000005.pdf')
        self.assertEqual(result, ('AM002868', 'CL-000005'))

    def test_match_training_record_filename_rejects_unrelated_name(self):
        self.assertIsNone(_match_training_record_filename('KetQuaThuViec_AM002868.pdf'))

    def test_parse_skill_percent_comma_fraction(self):
        self.assertEqual(_parse_skill_percent('0,94'), 94.0)

    def test_parse_skill_percent_already_percent_with_comma_decimal(self):
        self.assertEqual(_parse_skill_percent('94,5'), 94.5)

    def test_parse_skill_percent_plain_integer(self):
        self.assertEqual(_parse_skill_percent('94'), 94.0)

    def test_parse_skill_percent_blank_is_none(self):
        self.assertIsNone(_parse_skill_percent(''))
        self.assertIsNone(_parse_skill_percent(None))

    def test_parse_skill_result(self):
        self.assertEqual(_parse_skill_result('Đạt'), Evaluation.Result.PASS)
        self.assertEqual(_parse_skill_result('Không đạt'), Evaluation.Result.FAIL)
        self.assertEqual(_parse_skill_result(''), '')

    def test_parse_decimal_comma_keeps_fraction_scale(self):
        self.assertEqual(_parse_decimal_comma('0,94'), 0.94)
        self.assertEqual(_parse_decimal_comma('0.94'), 0.94)
        self.assertIsNone(_parse_decimal_comma(''))
        self.assertIsNone(_parse_decimal_comma(None))

    def test_parse_sheet_date_drops_time_part(self):
        self.assertEqual(_parse_sheet_date('2026-07-28'), datetime.date(2026, 7, 28))
        self.assertEqual(_parse_sheet_date('2026-07-28 10:30:00'), datetime.date(2026, 7, 28))
        self.assertEqual(_parse_sheet_date('2026-07-28T10:30:00'), datetime.date(2026, 7, 28))
        self.assertIsNone(_parse_sheet_date(''))
        self.assertIsNone(_parse_sheet_date('not-a-date'))


class ProcessAppEmployeesFieldsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='AM0001', name='A', restaurant=self.restaurant,
        )
        self.command = ImportJulyDataCommand()

    def test_no_row_leaves_employee_untouched_and_not_synced(self):
        stats = {'app_employees_synced': 0}

        self.command._process_app_employees_fields(self.employee, None, dry_run=False, stats=stats)

        self.assertEqual(stats['app_employees_synced'], 0)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.final_result, '')

    def test_dry_run_counts_but_does_not_write(self):
        row = {'Skill_Score_%': '0,94', 'Skill_Result': 'Đạt', 'Final_Probation_Result': 'Pass thử việc',
               'Pass_Date': '2026-07-28'}
        stats = {'app_employees_synced': 0}

        self.command._process_app_employees_fields(self.employee, row, dry_run=True, stats=stats)

        self.assertEqual(stats['app_employees_synced'], 1)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.final_result, '')
        self.assertIsNone(self.employee.pass_date)

    def test_confirm_writes_skill_and_final_result_and_pass_date_when_pass(self):
        row = {'Skill_Score_%': '0,94', 'Skill_Result': 'Đạt', 'Final_Probation_Result': 'Pass thử việc',
               'Pass_Date': '2026-07-28'}
        stats = {'app_employees_synced': 0}

        self.command._process_app_employees_fields(self.employee, row, dry_run=False, stats=stats)

        self.employee.refresh_from_db()
        self.assertEqual(float(self.employee.skill_score), 0.94)
        self.assertEqual(self.employee.skill_result, 'Đạt')
        self.assertEqual(self.employee.final_result, 'Pass thử việc')
        self.assertEqual(self.employee.pass_date, datetime.date(2026, 7, 28))

    def test_pass_date_not_set_when_final_result_is_not_pass(self):
        row = {'Final_Probation_Result': 'Tiếp tục thử việc', 'Pass_Date': '2026-07-28'}
        stats = {'app_employees_synced': 0}

        self.command._process_app_employees_fields(self.employee, row, dry_run=False, stats=stats)

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.final_result, 'Tiếp tục thử việc')
        self.assertIsNone(self.employee.pass_date)

    def test_resigned_at_set_when_resigned_date_present(self):
        row = {'Resigned_Date': '2026-07-15'}
        stats = {'app_employees_synced': 0}

        self.command._process_app_employees_fields(self.employee, row, dry_run=False, stats=stats)

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.resigned_at, datetime.date(2026, 7, 15))


class BuildChecklistCodeMapTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_matches_by_brand_position_task_name(self):
        c1 = Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name='An toàn vệ sinh',
        )
        sheet_rows = [{
            'Brand': ' Kampong ', 'Position': ' Phục vụ ', 'Task_Name': ' An toàn vệ sinh ',
            'Checklist_ID': 'CL-000001', 'Day': '1', 'Category': 'Onboarding',
        }]

        code_to_checklist, checklist_to_code, unmatched = build_checklist_code_map(self.tenant, sheet_rows)

        self.assertEqual(code_to_checklist['CL-000001'], c1)
        self.assertEqual(checklist_to_code[c1.id], 'CL-000001')
        self.assertEqual(unmatched, [])

    def test_skips_rows_with_empty_position(self):
        Checklist.objects.create(tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name='X')
        sheet_rows = [{'Brand': 'Kampong', 'Position': '', 'Task_Name': 'X', 'Checklist_ID': 'CL-000080'}]

        code_to_checklist, checklist_to_code, unmatched = build_checklist_code_map(self.tenant, sheet_rows)

        self.assertEqual(code_to_checklist, {})
        self.assertEqual(len(unmatched), 1)

    def test_disambiguates_duplicate_task_name_by_day_and_category(self):
        c1 = Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name='Ôn tập',
            day=1, category='Lý thuyết',
        )
        c2 = Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name='Ôn tập',
            day=2, category='Thực hành',
        )
        sheet_rows = [
            {'Brand': 'Kampong', 'Position': 'Phục vụ', 'Task_Name': 'Ôn tập', 'Day': '1',
             'Category': 'Lý thuyết', 'Checklist_ID': 'CL-000010'},
            {'Brand': 'Kampong', 'Position': 'Phục vụ', 'Task_Name': 'Ôn tập', 'Day': '2',
             'Category': 'Thực hành', 'Checklist_ID': 'CL-000011'},
        ]

        code_to_checklist, checklist_to_code, unmatched = build_checklist_code_map(self.tenant, sheet_rows)

        self.assertEqual(checklist_to_code[c1.id], 'CL-000010')
        self.assertEqual(checklist_to_code[c2.id], 'CL-000011')
        self.assertEqual(unmatched, [])

    def test_no_matching_row_is_unmatched(self):
        c1 = Checklist.objects.create(tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name='Không có trong sheet')

        code_to_checklist, checklist_to_code, unmatched = build_checklist_code_map(self.tenant, [])

        self.assertEqual(unmatched, [c1])
        self.assertEqual(code_to_checklist, {})

    def test_falls_back_to_already_saved_code_when_string_match_fails(self):
        c1 = Checklist.objects.create(
            tenant=self.tenant, brand='YYM', position='Phục vụ',
            task_name='Menu...\n(Tự đào tạo theo thực tế - chưa có SOP)', code='CL-000063',
        )
        sheet_rows = [{
            'Brand': 'YYM', 'Position': 'Phục vụ', 'Task_Name': 'Menu... (khac ban DB)',
            'Checklist_ID': 'CL-999999',
        }]

        code_to_checklist, checklist_to_code, unmatched = build_checklist_code_map(self.tenant, sheet_rows)

        self.assertEqual(code_to_checklist['CL-000063'], c1)
        self.assertEqual(checklist_to_code[c1.id], 'CL-000063')
        self.assertEqual(unmatched, [])
