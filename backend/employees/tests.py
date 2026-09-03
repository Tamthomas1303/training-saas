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
from checklist.models import Checklist, Document, TrainingProgress
from cls_sync.models import ExamResult, ExamScoreAdjustment
from accounts.services import update_grading_config
from employees.career import prerequisite_status, registration_status
from employees.dashboard import _month_end, _s_pass_rate_this_month
from employees.models import CurriculumItem, Employee, Position
from employees.services import (
    best_exam_score,
    change_employee_status,
    checklist_progress_by_phase,
    compute_final_result,
    emp_type,
    exam_pass,
    probation_checklist_ok,
    recompute_final_result,
)
from employees.management.commands.import_july_data import (
    Command as ImportJulyDataCommand,
)
from employees.management.commands.backfill_pass_date_from_sheet import (
    compute_pass_date_updates,
    diagnose_cohort,
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

    def test_exam_pass_default_threshold_follows_grading_config_not_hardcode(self):
        """UI dot 3 (Kiem thu dot 3, muc 2): doi GradingConfig.exam_pass_percent 80->75 phai lam
        lat ket qua dat/truot cua 1 diem thi bien (78 - truoc day truot vi < 80, sau khi ha
        nguong xuong 75 thi dat) - KHONG can truyen threshold= tay, dung mac dinh tu config."""
        from accounts.services import update_grading_config

        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('78.00'),
        )
        self.assertFalse(exam_pass(self.employee))  # 78 < 80 (mac dinh, khop hardcode cu)

        update_grading_config(self.tenant, None, {'exam_pass_percent': 75})
        self.assertTrue(exam_pass(self.employee))  # 78 >= 75 sau khi doi cau hinh


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

    def test_dashboard_exposes_total_new_prev_for_sparkline(self):
        """UI dot 2 (Prompt_UI_Dot2_ConsoleAdmin.md muc C) - total_new_prev la du lieu THAT (da
        tinh san tu truoc de ra total_new_delta), CHI moi lo ra them de FE ve sparkline 2 diem,
        khong doi cach tinh gi ca."""
        today = timezone.now().date()
        prev_month_date = today.replace(day=1) - datetime.timedelta(days=1)
        Employee.objects.create(tenant=self.tenant, code='S1', name='A', start_date=today)
        Employee.objects.create(tenant=self.tenant, code='S2', name='B', start_date=prev_month_date)
        Employee.objects.create(tenant=self.tenant, code='S3', name='C', start_date=prev_month_date)

        resp = self.client.get('/api/employees/dashboard/')
        stats = resp.data['stats']
        self.assertEqual(stats['total_new'], 1)
        self.assertEqual(stats['total_new_prev'], 2)


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


class ComputeFinalResultSkillThresholdGradingConfigTests(TestCase):
    """UI dot 3: nguong 'ky nang dat' (85) trong compute_final_result (cap Nhan vien thuong -
    cot Ket qua thu viec) phai doc GradingConfig.skill_pass_percent thay vi hardcode 85, cung mot
    khai niem voi cai da wire o probation_conditions() (dong bo, tranh admin doi 1 noi nhung noi
    khac van dung so cu)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', position='NV Phục vụ',
            operation_unit=Employee.OperationUnit.RESTAURANT, skill_score=Decimal('0.82'),
        )

    def _compute(self):
        from employees.services import compute_final_result

        with patch('employees.services.lms_done', return_value=True), \
             patch('employees.services.probation_checklist_ok', return_value=True), \
             patch('employees.services.exam_pass', return_value=True):
            return compute_final_result(self.employee)

    def test_82_percent_skill_fails_default_85_threshold(self):
        self.assertEqual(self._compute(), 'Tiếp tục thử việc')  # 82 < 85 (mac dinh, khop hardcode cu)

    def test_82_percent_skill_passes_after_lowering_threshold(self):
        from accounts.services import update_grading_config

        update_grading_config(self.tenant, None, {'skill_pass_percent': 80})
        self.assertEqual(self._compute(), 'Pass thử việc')  # 82 >= 80 sau khi ha nguong


class BatchLmsMarksEmptyListTests(TestCase):
    """Hoi quy: batch_lms_marks([]) phai tra ve {} thay vi crash (xem EmployeeListTabTests.
    test_tab_with_zero_matches_returns_empty_list_not_500 cho kich ban qua API that su)."""

    def test_empty_list_returns_empty_dict(self):
        from employees.services import batch_lms_marks

        self.assertEqual(batch_lms_marks([]), {})


class EmployeeListTabTests(TestCase):
    """Nhom 1 muc A + Prompt_Fix_3Tab_NhanSu.md: 3 tab danh sach nhan su qua ?list_tab=, dinh
    nghia LAI theo is_legacy (dinh nghia cu dung employee_status='probation' cho tab 'new' lam
    tab trong tren tenant that vi hau het nhan su moi da qua thu viec - xem fix)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

        # Nhan su moi (tu 1/7/2026), dang thu viec - CHI o tab 'new'.
        self.probation_emp = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='Dang thu viec', is_legacy=False,
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        # Nhan su moi DA PASS thu viec - phai xuat hien o CA 'new' VA 'active' (dung y prompt:
        # "1 nguoi co the o CA 2 tab").
        self.new_passed_emp = Employee.objects.create(
            tenant=self.tenant, code='NV2', name='Moi da pass', is_legacy=False,
            employee_status=Employee.EmployeeStatus.ACTIVE, position='Phục vụ', level_group='S',
        )
        # Nhan su CU (truoc 1/7/2026, nap tu lich su) - CHI o tab 'active', KHONG o tab 'new'.
        self.legacy_emp = Employee.objects.create(
            tenant=self.tenant, code='NV4', name='Nhan su cu', is_legacy=True,
            employee_status=Employee.EmployeeStatus.ACTIVE, position='Phục vụ', level_group='S',
        )
        # Cap O (Ban quan ly) - CHI o tab 'management', khong o 'active' du employee_status=active.
        self.mgmt_emp = Employee.objects.create(
            tenant=self.tenant, code='NV3', name='Quản lý nhà hàng', is_legacy=False,
            employee_status=Employee.EmployeeStatus.ACTIVE, position='Quản lý nhà hàng', level_group='O',
        )
        # Da nghi viec - KHONG o 'active' lan 'management' du truoc do la cap O/active.
        self.resigned_emp = Employee.objects.create(
            tenant=self.tenant, code='NV5', name='Da nghi viec', is_legacy=True,
            employee_status=Employee.EmployeeStatus.RESIGNED, level_group='S',
        )

    def _codes(self, list_tab):
        resp = self.client.get(reverse('employee-list'), {'list_tab': list_tab, 'page_size': 50})
        return {row['code'] for row in resp.data['results']}

    def test_new_tab_is_all_non_legacy_regardless_of_status(self):
        """Dinh nghia moi: is_legacy=False - gom CA dang thu viec LAN da pass (khong loc theo
        employee_status), KHONG con bi trong khi tenant da qua thu viec het."""
        self.assertEqual(self._codes('new'), {'NV1', 'NV2', 'NV3'})

    def test_active_tab_includes_legacy_and_passed_new_excludes_management_and_resigned(self):
        self.assertEqual(self._codes('active'), {'NV2', 'NV4'})

    def test_new_passed_employee_appears_in_both_new_and_active_tabs(self):
        """Dung y prompt: 1 nhan su moi da pass phai co mat o CA 2 tab, khong loai tru nhau."""
        self.assertIn('NV2', self._codes('new'))
        self.assertIn('NV2', self._codes('active'))

    def test_management_tab_is_level_group_o(self):
        self.assertEqual(self._codes('management'), {'NV3'})

    def test_no_list_tab_returns_everyone(self):
        self.assertEqual(self._codes(''), {'NV1', 'NV2', 'NV3', 'NV4', 'NV5'})

    def test_tab_with_zero_matches_returns_empty_list_not_500(self):
        """Hoi quy: neu list_tab loc ra 0 dong, API phai tra ve danh sach RONG, KHONG duoc 500
        (xem fix batch_lms_marks - truoc day threshold=None khi employees rong lam
        computed_score__gte=None → ValueError 'Cannot use None as a query value')."""
        Employee.objects.all().delete()  # khong con ai -> ca 3 tab deu ra 0 dong
        resp = self.client.get(reverse('employee-list'), {'list_tab': 'new', 'page_size': 50})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'], [])

    def test_active_and_management_rows_expose_exam_score(self):
        from decimal import Decimal as D

        ExamResult.objects.create(
            tenant=self.tenant, employee=self.new_passed_emp, exam_name='15N', attempt=1, score=D('88.00'),
        )
        resp = self.client.get(reverse('employee-list'), {'list_tab': 'active', 'page_size': 50})
        row = next(r for r in resp.data['results'] if r['code'] == 'NV2')
        self.assertEqual(float(row['exam_score']), 88.0)


class StudentDetailCoursesExamAttemptsTests(TestCase):
    """Nhom 1 muc B.2/B.3: /employees/<id>/detail/ tra them 'courses' + 'exam_attempts'."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_detail_includes_courses_and_exam_attempts_keys(self):
        resp = self.client.get(reverse('employee-student-detail', args=[self.employee.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('courses', resp.data)
        self.assertIn('exam_attempts', resp.data)
        self.assertEqual(resp.data['courses'], [])
        self.assertEqual(resp.data['exam_attempts'], [])

    def test_detail_includes_enrolled_course_progress(self):
        from courses.models import Course, Enrollment

        course = Course.objects.create(tenant=self.tenant, title='Khóa demo', status='published')
        Enrollment.objects.create(tenant=self.tenant, course=course, employee=self.employee)
        resp = self.client.get(reverse('employee-student-detail', args=[self.employee.id]))
        self.assertEqual(len(resp.data['courses']), 1)
        self.assertEqual(resp.data['courses'][0]['title'], 'Khóa demo')


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


class BackfillPassDateFromSheetTests(TestCase):
    """Prompt_Fix_PassDate_DungLoTrinh.md: sua pass_date SAI (khong phai RONG) do loi parser cu
    khong doc duoc dinh dang JS Date.toString() cua cot Pass_Date tren Sheet app_employees -
    doc lai tu Sheet (da sua parser) va cap nhat pass_date cho nhan su dang Pass ma gia tri
    khac Sheet, KHONG dong vao nguoi chua Pass."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')

    def _employee(self, code, **kwargs):
        defaults = dict(
            tenant=self.tenant, code=code, name=code, position='NV Phục vụ', restaurant=self.restaurant,
            operation_unit=Employee.OperationUnit.RESTAURANT, employee_status='active',
        )
        defaults.update(kwargs)
        return Employee.objects.create(**defaults)

    @patch('employees.management.commands.backfill_pass_date_from_sheet.load_csv_rows')
    def test_backfills_wrong_pass_date_from_sheet(self, mock_load):
        # DB pass_date=28/7 (tu 1 lan recompute chay sau, SAI) nhung Sheet "chot" ghi 21/7.
        e = self._employee(
            'NV1', final_result='Pass thử việc',
            start_date=datetime.date(2026, 7, 6), pass_date=datetime.date(2026, 7, 28),
        )
        mock_load.return_value = [{
            'Employee_ID': 'NV1', 'Pass_Date': 'Wed Jul 21 2026 14:00:00 GMT+0700 (Indochina Time)',
        }]

        call_command('backfill_pass_date_from_sheet', tenant='Demo Tenant', csv_url='http://fake', month=7, year=2026)

        e.refresh_from_db()
        self.assertEqual(e.pass_date, datetime.date(2026, 7, 21))

    @patch('employees.management.commands.backfill_pass_date_from_sheet.load_csv_rows')
    def test_dry_run_does_not_write(self, mock_load):
        e = self._employee(
            'NV1', final_result='Pass thử việc',
            start_date=datetime.date(2026, 7, 6), pass_date=datetime.date(2026, 7, 28),
        )
        mock_load.return_value = [{'Employee_ID': 'NV1', 'Pass_Date': '2026-07-21'}]

        call_command(
            'backfill_pass_date_from_sheet', tenant='Demo Tenant', csv_url='http://fake',
            month=7, year=2026, dry_run=True,
        )

        e.refresh_from_db()
        self.assertEqual(e.pass_date, datetime.date(2026, 7, 28))

    @patch('employees.management.commands.backfill_pass_date_from_sheet.load_csv_rows')
    def test_idempotent_second_run_makes_no_further_changes(self, mock_load):
        e = self._employee(
            'NV1', final_result='Pass thử việc',
            start_date=datetime.date(2026, 7, 6), pass_date=datetime.date(2026, 7, 28),
        )
        mock_load.return_value = [{'Employee_ID': 'NV1', 'Pass_Date': '2026-07-21'}]

        call_command('backfill_pass_date_from_sheet', tenant='Demo Tenant', csv_url='http://fake', month=7, year=2026)
        call_command('backfill_pass_date_from_sheet', tenant='Demo Tenant', csv_url='http://fake', month=7, year=2026)

        e.refresh_from_db()
        self.assertEqual(e.pass_date, datetime.date(2026, 7, 21))

    @patch('employees.management.commands.backfill_pass_date_from_sheet.load_csv_rows')
    def test_does_not_touch_employee_not_marked_pass(self, mock_load):
        e = self._employee(
            'NV1', final_result='Tiếp tục thử việc',
            start_date=datetime.date(2026, 7, 6), pass_date=None,
        )
        mock_load.return_value = [{'Employee_ID': 'NV1', 'Pass_Date': '2026-07-21'}]

        call_command('backfill_pass_date_from_sheet', tenant='Demo Tenant', csv_url='http://fake', month=7, year=2026)

        e.refresh_from_db()
        self.assertIsNone(e.pass_date)

    @patch('employees.management.commands.backfill_pass_date_from_sheet.load_csv_rows')
    def test_no_matching_sheet_row_or_invalid_date_skipped(self, mock_load):
        e = self._employee(
            'NV1', final_result='Pass thử việc',
            start_date=datetime.date(2026, 7, 6), pass_date=datetime.date(2026, 7, 28),
        )
        mock_load.return_value = [{'Employee_ID': 'OTHER', 'Pass_Date': '2026-07-21'}]

        call_command('backfill_pass_date_from_sheet', tenant='Demo Tenant', csv_url='http://fake', month=7, year=2026)

        e.refresh_from_db()
        self.assertEqual(e.pass_date, datetime.date(2026, 7, 28))

    @patch('employees.management.commands.backfill_pass_date_from_sheet.load_csv_rows')
    def test_diagnosis_before_after_reflects_on_time_rate_change(self, mock_load):
        self._employee(
            'NV1', final_result='Pass thử việc',
            start_date=datetime.date(2026, 7, 6), pass_date=datetime.date(2026, 7, 28),
        )
        mock_load.return_value = [{'Employee_ID': 'NV1', 'Pass_Date': '2026-07-21'}]

        before = diagnose_cohort(self.tenant, 7, 2026)
        self.assertEqual(before['pass_count'], 1)
        self.assertEqual(before['with_pass_date'], 1)
        self.assertEqual(before['on_time'], 0)

        call_command('backfill_pass_date_from_sheet', tenant='Demo Tenant', csv_url='http://fake', month=7, year=2026)

        after = diagnose_cohort(self.tenant, 7, 2026)
        self.assertEqual(after['on_time'], 1)
        self.assertEqual(after['on_time_rate'], 100.0)

    @patch('employees.management.commands.backfill_pass_date_from_sheet.load_csv_rows')
    def test_compute_pass_date_updates_counts_reasons_for_skipping(self, mock_load):
        e1 = self._employee('NV1', final_result='Pass thử việc', pass_date=datetime.date(2026, 7, 28))
        self._employee('NV2', final_result='Pass thử việc', pass_date=datetime.date(2026, 7, 21))  # da khop san
        rows = [
            {'Employee_ID': 'NV1', 'Pass_Date': '2026-07-21'},
            {'Employee_ID': 'NV2', 'Pass_Date': '2026-07-21'},
        ]

        plan = compute_pass_date_updates(self.tenant, rows)

        self.assertEqual([e.code for e, _ in plan['to_update']], ['NV1'])
        self.assertEqual(plan['to_update'][0][1], datetime.date(2026, 7, 21))
        self.assertEqual(plan['already_match'], 1)
        self.assertEqual(e1.pass_date, datetime.date(2026, 7, 28))  # chua ghi, chi tinh toan


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

    def test_parse_sheet_date_handles_js_date_tostring_format(self):
        """Prompt_Fix_PassDate_DungLoTrinh.md: cot Pass_Date/Resigned_Date tren Sheet
        app_employees thuc te o dang JS Date.toString() (o co cong thuc =NOW()/new Date()),
        TRUOC KHI SUA ham nay tra None cho dinh dang nay (nem ValueError tu token dau 'Wed')
        -> import am tham bo qua viec ghi pass_date."""
        self.assertEqual(
            _parse_sheet_date('Wed Jul 29 2026 14:01:38 GMT+0700 (Indochina Time)'),
            datetime.date(2026, 7, 29),
        )
        self.assertEqual(
            _parse_sheet_date('Fri Jul 31 2026 17:09:00 GMT+0700 (Indochina Time)'),
            datetime.date(2026, 7, 31),
        )
        # Dinh dang khac (khong phai ISO, khong phai JS Date.toString() 4-token) - van None,
        # khong doan bua.
        self.assertIsNone(_parse_sheet_date('01/07/2026'))


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

    def test_confirm_writes_pass_date_from_js_date_tostring_format(self):
        """Prompt_Fix_PassDate_DungLoTrinh.md: dinh dang Pass_Date thuc te tren Sheet (JS
        Date.toString()) gio phai duoc ghi dung, khong con bi am tham bo qua."""
        row = {
            'Final_Probation_Result': 'Pass thử việc',
            'Pass_Date': 'Wed Jul 29 2026 14:01:38 GMT+0700 (Indochina Time)',
        }
        stats = {'app_employees_synced': 0}

        self.command._process_app_employees_fields(self.employee, row, dry_run=False, stats=stats)

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.final_result, 'Pass thử việc')
        self.assertEqual(self.employee.pass_date, datetime.date(2026, 7, 29))

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


class StudentDetailLoginUsernameTests(TestCase):
    """student_info tra ve login_username (module Khoa hoc, MVP dot 1) - '' khi chua tao tai
    khoan, username khi da co (Employee.user)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1')
        self.client = APIClient()

    def test_login_username_blank_when_no_account(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('employee-student-detail', args=[self.employee.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['info']['login_username'], '')

    def test_login_username_populated_when_linked(self):
        learner = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        self.employee.user = learner
        self.employee.save(update_fields=['user'])

        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('employee-student-detail', args=[self.employee.id]))
        self.assertEqual(resp.data['info']['login_username'], 'nv1')


class OnboardingAutomationTests(TestCase):
    """Nhom 3A (Prompt_Nhom3A_Onboarding_TuDong.md): run_onboarding_for_new - 3 cong tac
    (tao tai khoan / auto-enroll / email tiep nhan), idempotent, bo qua nhan su cu."""

    def setUp(self):
        from courses.models import Course

        from .models import AutomationSettings, OnboardingCourseRule

        mail.outbox = []
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(
            tenant=self.tenant, code='NH1', name='Nhà hàng 1', email='qlnh1@example.com',
        )
        self.course = Course.objects.create(tenant=self.tenant, title='Khóa hội nhập', status='published')
        OnboardingCourseRule.objects.create(tenant=self.tenant, position='NV Phục vụ', course=self.course)
        self.settings_obj = AutomationSettings.objects.create(
            tenant=self.tenant,
            auto_create_account=True, auto_enroll_onboarding=True, send_welcome_email=True,
            welcome_email_subject='Chào {ten_nhan_su}',
            welcome_email_body='Xin chào {ten_nhan_su}, đặt mật khẩu tại {link_dat_mat_khau} (đăng nhập: {ten_dang_nhap})',
        )

    def _new_employee(self, code='NV1'):
        return Employee.objects.create(
            tenant=self.tenant, code=code, name='Nhân sự mới', position='NV Phục vụ',
            restaurant=self.restaurant, is_legacy=False,
        )

    def test_creates_account_enrolls_and_sends_welcome_email(self):
        from courses.models import Enrollment
        from accounts.models import PasswordSetToken

        from .automation import run_onboarding_for_new

        employee = self._new_employee()
        result = run_onboarding_for_new(employee)

        employee.refresh_from_db()
        self.assertIsNotNone(employee.user_id)
        self.assertEqual(employee.user.role, User.Role.EMPLOYEE)
        self.assertFalse(employee.user.has_usable_password())

        token = PasswordSetToken.objects.get(user=employee.user)
        self.assertIsNone(token.used_at)
        self.assertTrue(token.is_valid())

        enrollment = Enrollment.objects.get(employee=employee, course=self.course)
        self.assertEqual(enrollment.source, Enrollment.Source.AUTO)

        self.assertTrue(result['account_created'])
        self.assertEqual(result['enrolled_courses'], [self.course.id])
        self.assertTrue(result['email_sent'])
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['qlnh1@example.com'])
        self.assertIn(f'token={token.token}', sent.body)
        # Khong bao gio kem mat khau tho trong email - luong nay khong sinh mat khau nao ca
        # (set_unusable_password() ngay tu dau, chi co link dat mat khau qua token).
        self.assertNotIn('mật khẩu:', sent.body.lower())

    def test_idempotent_rerun_does_not_duplicate(self):
        from accounts.models import PasswordSetToken
        from courses.models import Enrollment

        from .automation import run_onboarding_for_new

        employee = self._new_employee()
        run_onboarding_for_new(employee)
        employee.refresh_from_db()
        first_user_id = employee.user_id

        run_onboarding_for_new(employee)
        employee.refresh_from_db()

        self.assertEqual(employee.user_id, first_user_id)
        self.assertEqual(User.objects.filter(id=first_user_id).count(), 1)
        self.assertEqual(PasswordSetToken.objects.filter(user_id=first_user_id).count(), 1)
        self.assertEqual(Enrollment.objects.filter(employee=employee, course=self.course).count(), 1)
        # Lan 2 khong tao token moi nen KHONG gui lai email tiep nhan.
        self.assertEqual(len(mail.outbox), 1)

    def test_legacy_employee_is_skipped_entirely(self):
        from courses.models import Enrollment

        employee = Employee.objects.create(
            tenant=self.tenant, code='NVCU', name='Nhân sự cũ', position='NV Phục vụ',
            restaurant=self.restaurant, is_legacy=True,
        )
        from .automation import run_onboarding_for_new

        result = run_onboarding_for_new(employee)

        self.assertIsNone(result)
        employee.refresh_from_db()
        self.assertIsNone(employee.user_id)
        self.assertFalse(Enrollment.objects.filter(employee=employee).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_toggle_off_auto_enroll_skips_enrollment(self):
        from courses.models import Enrollment

        self.settings_obj.auto_enroll_onboarding = False
        self.settings_obj.save(update_fields=['auto_enroll_onboarding'])

        from .automation import run_onboarding_for_new

        employee = self._new_employee()
        run_onboarding_for_new(employee)

        employee.refresh_from_db()
        self.assertIsNotNone(employee.user_id)
        self.assertFalse(Enrollment.objects.filter(employee=employee).exists())

    def test_no_email_when_restaurant_has_no_email(self):
        self.restaurant.email = ''
        self.restaurant.save(update_fields=['email'])

        from .automation import run_onboarding_for_new

        employee = self._new_employee()
        result = run_onboarding_for_new(employee)

        self.assertFalse(result['email_sent'])
        self.assertEqual(len(mail.outbox), 0)


class IngestEmployeesOnboardingHookTests(TestCase):
    """Nhom 3A muc 2: ingest_employees (recruitment.py, dung boi RecruitmentSyncNowView/
    RecruitmentImportFileView) phai chay onboarding tu dong cho nhan su MOI TAO, va KHONG chay
    lai (khong tao trung tai khoan) khi import lai cung nhan su."""

    def setUp(self):
        from .models import AutomationSettings

        mail.outbox = []
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(
            tenant=self.tenant, code='NH1', name='Nhà hàng 1', email='qlnh1@example.com',
        )
        AutomationSettings.objects.create(tenant=self.tenant, auto_create_account=True)

    def test_ingest_creates_account_for_newly_created_employee(self):
        from .recruitment import ingest_employees

        rows = [{
            'Employee_ID': 'NV1', 'Employee_Name': 'Nhân sự mới',
            'Restaurant_ID': str(self.restaurant.id), 'Job_Position': 'NV Phục vụ',
        }]
        stats = ingest_employees(self.tenant, rows)

        self.assertEqual(stats['created'], 1)
        self.assertEqual(stats['onboarding_ok'], 1)
        self.assertEqual(stats['onboarding_failed'], 0)
        employee = Employee.objects.get(tenant=self.tenant, code='NV1')
        self.assertIsNotNone(employee.user_id)

    def test_reimport_same_employee_does_not_duplicate_account(self):
        from .recruitment import ingest_employees

        rows = [{
            'Employee_ID': 'NV1', 'Employee_Name': 'Nhân sự mới',
            'Restaurant_ID': str(self.restaurant.id), 'Job_Position': 'NV Phục vụ',
        }]
        ingest_employees(self.tenant, rows)
        employee = Employee.objects.get(tenant=self.tenant, code='NV1')
        first_user_id = employee.user_id

        stats2 = ingest_employees(self.tenant, rows)
        employee.refresh_from_db()

        self.assertEqual(stats2['created'], 0)
        self.assertEqual(stats2['updated'], 1)
        self.assertEqual(stats2['onboarding_ok'], 0)
        self.assertEqual(employee.user_id, first_user_id)
        self.assertEqual(User.objects.filter(tenant=self.tenant).count(), 1)


class AutomationSettingsApiTests(TestCase):
    """Nhom 3A muc 4: GET/PUT /api/employees/automation-settings/ + CRUD
    /api/employees/onboarding-course-rules/ - chi Admin."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.client = APIClient()

    def test_get_creates_default_settings_for_tenant(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('automation-settings'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['auto_create_account'])

    def test_put_updates_3_toggles_and_template(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.put(reverse('automation-settings'), {
            'auto_create_account': True, 'auto_enroll_onboarding': True, 'send_welcome_email': True,
            'welcome_email_body': 'Link: {link_dat_mat_khau}',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['auto_create_account'])
        self.assertTrue(resp.data['auto_enroll_onboarding'])
        self.assertTrue(resp.data['send_welcome_email'])
        self.assertIn('{link_dat_mat_khau}', resp.data['welcome_email_body'])

    def test_non_admin_forbidden(self):
        self.client.force_authenticate(self.om)
        resp = self.client.get(reverse('automation-settings'))
        self.assertEqual(resp.status_code, 403)

    def test_course_rule_crud(self):
        from courses.models import Course

        course = Course.objects.create(tenant=self.tenant, title='Khóa hội nhập', status='published')
        self.client.force_authenticate(self.admin)

        resp = self.client.post(
            reverse('onboarding-course-rule-list'), {'position': 'NV Phục vụ', 'course': course.id}, format='json',
        )
        self.assertEqual(resp.status_code, 201)
        rule_id = resp.data['id']
        self.assertEqual(resp.data['course_title'], 'Khóa hội nhập')

        list_resp = self.client.get(reverse('onboarding-course-rule-list'))
        self.assertEqual(list_resp.status_code, 200)
        results = list_resp.data.get('results', list_resp.data)
        self.assertEqual(len(results), 1)

        del_resp = self.client.delete(reverse('onboarding-course-rule-detail', args=[rule_id]))
        self.assertEqual(del_resp.status_code, 204)


class ProbationExamEligibilityTests(TestCase):
    """Nhom 3B (Prompt_Nhom3B_ThiThuViec_TuDong.md muc 2): check_probation_exam_eligibility -
    dieu kien vao hang doi "Cho duyet thi". Mock lms_done/probation_checklist_ok (da co test
    rieng o noi khac) de tap trung vao logic cong tac/rule/idempotency cua ham nay."""

    def setUp(self):
        from exams.models import Assessment

        from employees.models import AutomationSettings, ProbationExamRule

        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='Nhà hàng 1')
        self.assessment = Assessment.objects.create(
            tenant=self.tenant, title='Thi thử việc Phục vụ', status='published',
        )
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='Nhân viên A', position='NV Phục vụ',
            restaurant=self.restaurant, is_legacy=False,
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        self.settings_obj = AutomationSettings.objects.create(
            tenant=self.tenant, auto_assign_probation_exam=True, require_approval_before_exam=True,
        )
        ProbationExamRule.objects.create(tenant=self.tenant, position='NV Phục vụ', assessment=self.assessment)

    @patch('employees.services.probation_checklist_ok', return_value=True)
    @patch('employees.services.lms_done', return_value=True)
    def test_eligible_employee_creates_pending_candidate_not_yet_assigned(self, mock_lms, mock_checklist):
        from employees.automation import check_probation_exam_eligibility
        from employees.models import ProbationExamCandidate
        from exams.models import AssessmentAssignment

        candidate = check_probation_exam_eligibility(self.employee)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.status, ProbationExamCandidate.Status.PENDING_APPROVAL)
        self.assertEqual(ProbationExamCandidate.objects.filter(employee=self.employee).count(), 1)
        self.assertFalse(AssessmentAssignment.objects.filter(employee=self.employee).exists())

    @patch('employees.services.probation_checklist_ok', return_value=True)
    @patch('employees.services.lms_done', return_value=True)
    def test_idempotent_no_duplicate_candidate(self, mock_lms, mock_checklist):
        from employees.automation import check_probation_exam_eligibility
        from employees.models import ProbationExamCandidate

        first = check_probation_exam_eligibility(self.employee)
        second = check_probation_exam_eligibility(self.employee)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(ProbationExamCandidate.objects.filter(employee=self.employee).count(), 1)

    @patch('employees.services.probation_checklist_ok', return_value=False)
    @patch('employees.services.lms_done', return_value=True)
    def test_checklist_below_100_percent_not_eligible(self, mock_lms, mock_checklist):
        from employees.automation import check_probation_exam_eligibility

        self.assertIsNone(check_probation_exam_eligibility(self.employee))

    @patch('employees.services.probation_checklist_ok', return_value=True)
    @patch('employees.services.lms_done', return_value=False)
    def test_lms_not_done_not_eligible(self, mock_lms, mock_checklist):
        from employees.automation import check_probation_exam_eligibility

        self.assertIsNone(check_probation_exam_eligibility(self.employee))

    @patch('employees.services.probation_checklist_ok', return_value=True)
    @patch('employees.services.lms_done', return_value=True)
    def test_toggle_off_auto_assign_skips(self, mock_lms, mock_checklist):
        self.settings_obj.auto_assign_probation_exam = False
        self.settings_obj.save(update_fields=['auto_assign_probation_exam'])
        from employees.automation import check_probation_exam_eligibility

        self.assertIsNone(check_probation_exam_eligibility(self.employee))

    @patch('employees.services.probation_checklist_ok', return_value=True)
    @patch('employees.services.lms_done', return_value=True)
    def test_legacy_employee_never_enters_queue(self, mock_lms, mock_checklist):
        legacy = Employee.objects.create(
            tenant=self.tenant, code='NVCU', name='Cũ', position='NV Phục vụ', is_legacy=True,
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        from employees.automation import check_probation_exam_eligibility

        self.assertIsNone(check_probation_exam_eligibility(legacy))

    @patch('employees.services.probation_checklist_ok', return_value=True)
    @patch('employees.services.lms_done', return_value=True)
    def test_no_matching_rule_not_eligible(self, mock_lms, mock_checklist):
        from employees.automation import check_probation_exam_eligibility

        other = Employee.objects.create(
            tenant=self.tenant, code='NV2', name='B', position='Bếp trưởng',
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        self.assertIsNone(check_probation_exam_eligibility(other))

    @patch('employees.services.probation_checklist_ok', return_value=True)
    @patch('employees.services.lms_done', return_value=True)
    def test_not_in_probation_status_not_eligible(self, mock_lms, mock_checklist):
        self.employee.employee_status = Employee.EmployeeStatus.ACTIVE
        self.employee.save(update_fields=['employee_status'])
        from employees.automation import check_probation_exam_eligibility

        self.assertIsNone(check_probation_exam_eligibility(self.employee))

    @patch('employees.services.probation_checklist_ok', return_value=True)
    @patch('employees.services.lms_done', return_value=True)
    def test_require_approval_false_auto_approves_immediately(self, mock_lms, mock_checklist):
        self.settings_obj.require_approval_before_exam = False
        self.settings_obj.save(update_fields=['require_approval_before_exam'])
        from employees.automation import check_probation_exam_eligibility
        from employees.models import ProbationExamCandidate
        from exams.models import AssessmentAssignment

        candidate = check_probation_exam_eligibility(self.employee)
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, ProbationExamCandidate.Status.APPROVED)
        self.assertTrue(
            AssessmentAssignment.objects.filter(employee=self.employee, assessment=self.assessment).exists()
        )


class ProbationExamApprovalTests(TestCase):
    """Nhom 3B muc 2: duyet/tu choi 1 ung vien trong hang doi "Cho duyet thi" + coi thi camera."""

    def setUp(self):
        from exams.models import Assessment
        from employees.models import ProbationExamCandidate

        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.assessment = Assessment.objects.create(
            tenant=self.tenant, title='Thi thử việc', status='published', max_attempts=1,
        )
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', position='NV Phục vụ',
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        self.candidate = ProbationExamCandidate.objects.create(
            tenant=self.tenant, employee=self.employee, assessment=self.assessment,
        )
        self.client = APIClient()

    def _add_question(self):
        from exams.models import AssessmentQuestion, Question, QuestionBank, QuestionOption

        bank = QuestionBank.objects.create(tenant=self.tenant, name='Bank')
        q = Question.objects.create(tenant=self.tenant, bank=bank, type=Question.Type.SINGLE, stem_html='Q1', points=1)
        QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='A', is_correct=True)
        QuestionOption.objects.create(tenant=self.tenant, question=q, content_html='B')
        AssessmentQuestion.objects.create(tenant=self.tenant, assessment=self.assessment, question=q)

    def test_employee_cannot_start_attempt_before_approval(self):
        from exams.services import ValidationError, start_attempt

        with self.assertRaises(ValidationError):
            start_attempt(self.employee, self.assessment)

    def test_approve_creates_session_and_allows_attempt_within_window(self):
        from employees.automation import approve_probation_exam_candidate
        from employees.models import ProbationExamCandidate
        from exams.services import start_attempt

        self._add_question()
        approve_probation_exam_candidate(self.candidate, self.admin)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, ProbationExamCandidate.Status.APPROVED)
        attempt = start_attempt(self.employee, self.assessment)
        self.assertIsNotNone(attempt.id)

    def test_attempt_blocked_outside_session_window(self):
        from employees.automation import approve_probation_exam_candidate
        from exams.services import ValidationError, start_attempt

        self._add_question()
        approve_probation_exam_candidate(
            self.candidate, self.admin, start_at=timezone.now() + datetime.timedelta(days=1),
        )
        with self.assertRaises(ValidationError):
            start_attempt(self.employee, self.assessment)

    def test_reject_leaves_no_assignment_with_reason_recorded(self):
        from employees.automation import reject_probation_exam_candidate
        from employees.models import ProbationExamCandidate
        from exams.services import ValidationError, start_attempt

        reject_probation_exam_candidate(self.candidate, self.admin, reason='Chưa đủ tiêu chuẩn')
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, ProbationExamCandidate.Status.REJECTED)
        self.assertEqual(self.candidate.reject_reason, 'Chưa đủ tiêu chuẩn')
        with self.assertRaises(ValidationError):
            start_attempt(self.employee, self.assessment)

    def test_cannot_approve_twice(self):
        from employees.automation import approve_probation_exam_candidate

        approve_probation_exam_candidate(self.candidate, self.admin)
        with self.assertRaises(ValueError):
            approve_probation_exam_candidate(self.candidate, self.admin)

    def test_camera_supervision_enables_proctoring_and_assigns_proctors(self):
        from employees.automation import approve_probation_exam_candidate

        approve_probation_exam_candidate(
            self.candidate, self.admin, supervised_by_restaurant_camera=True, proctor_ids=[self.trainer.id],
        )
        self.candidate.refresh_from_db()
        self.assessment.refresh_from_db()
        self.assertTrue(self.assessment.proctoring_enabled)
        self.assertTrue(self.candidate.exam_session.supervised_by_restaurant_camera)
        self.assertIn(self.trainer, self.candidate.exam_session.proctors.all())

    def test_list_view_requires_admin_or_trainer(self):
        self.client.force_authenticate(self.om)
        resp = self.client.get(reverse('probation-exam-candidate-list'))
        self.assertEqual(resp.status_code, 403)

    def test_list_view_defaults_to_pending_approval(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('probation-exam-candidate-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['employee_code'], 'NV1')

    def test_trainer_can_approve_via_api(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(reverse('probation-exam-candidate-approve', args=[self.candidate.id]), {}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'approved')

    def test_reject_via_api_with_reason(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse('probation-exam-candidate-reject', args=[self.candidate.id]), {'reason': 'x'}, format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'rejected')


class ProbationExamRuleApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_rule_crud(self):
        from exams.models import Assessment

        assessment = Assessment.objects.create(tenant=self.tenant, title='Thi thử việc', status='published')
        resp = self.client.post(
            reverse('probation-exam-rule-list'), {'position': 'NV Phục vụ', 'assessment': assessment.id}, format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['assessment_title'], 'Thi thử việc')

        del_resp = self.client.delete(reverse('probation-exam-rule-detail', args=[resp.data['id']]))
        self.assertEqual(del_resp.status_code, 204)


class ProbationResultNotificationTests(TestCase):
    """Nhom 3B luong 5 (Prompt_Nhom3B_ThiThuViec_TuDong.md muc 4): tu gui ket qua thu viec + moc
    luong, idempotent theo (employee, result, decision_date)."""

    def setUp(self):
        from employees.models import AutomationSettings

        mail.outbox = []
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(
            tenant=self.tenant, code='NH1', name='Nhà hàng 1', email='qlnh1@example.com',
        )
        self.settings_obj = AutomationSettings.objects.create(tenant=self.tenant, auto_send_probation_result=True)

    def _employee(self, code):
        return Employee.objects.create(
            tenant=self.tenant, code=code, name=f'NV {code}', restaurant=self.restaurant, position='NV Phục vụ',
        )

    def test_pass_sends_email_with_salary_date_pass_date_rule(self):
        from employees.automation import notify_probation_result_if_needed

        employee = self._employee('NV1')
        notify_probation_result_if_needed(employee, 'pass', datetime.date(2026, 8, 15))
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['qlnh1@example.com'])
        self.assertIn('15/08/2026', sent.body)

    def test_pass_next_month_first_rule_rolls_over_december(self):
        from employees.automation import notify_probation_result_if_needed
        from employees.models import AutomationSettings

        self.settings_obj.salary_effective_rule = AutomationSettings.SalaryEffectiveRule.NEXT_MONTH_FIRST
        self.settings_obj.save(update_fields=['salary_effective_rule'])
        employee = self._employee('NV2')
        notify_probation_result_if_needed(employee, 'pass', datetime.date(2026, 12, 20))
        self.assertIn('01/01/2027', mail.outbox[0].body)

    def test_idempotent_no_resend_for_same_decision(self):
        from employees.automation import notify_probation_result_if_needed

        employee = self._employee('NV3')
        notify_probation_result_if_needed(employee, 'pass', datetime.date(2026, 8, 15))
        notify_probation_result_if_needed(employee, 'pass', datetime.date(2026, 8, 15))
        self.assertEqual(len(mail.outbox), 1)

    def test_new_decision_date_sends_again(self):
        from employees.automation import notify_probation_result_if_needed

        employee = self._employee('NV4')
        notify_probation_result_if_needed(employee, 'pass', datetime.date(2026, 8, 15))
        notify_probation_result_if_needed(employee, 'pass', datetime.date(2026, 9, 1))
        self.assertEqual(len(mail.outbox), 2)

    def test_toggle_off_no_email(self):
        self.settings_obj.auto_send_probation_result = False
        self.settings_obj.save(update_fields=['auto_send_probation_result'])
        from employees.automation import notify_probation_result_if_needed

        employee = self._employee('NV5')
        notify_probation_result_if_needed(employee, 'pass', datetime.date(2026, 8, 15))
        self.assertEqual(len(mail.outbox), 0)

    def test_legacy_employee_no_email(self):
        from employees.automation import notify_probation_result_if_needed

        employee = Employee.objects.create(
            tenant=self.tenant, code='NV6', name='F', restaurant=self.restaurant, position='NV Phục vụ',
            is_legacy=True,
        )
        notify_probation_result_if_needed(employee, 'pass', datetime.date(2026, 8, 15))
        self.assertEqual(len(mail.outbox), 0)

    def test_failed_result_email_has_no_salary_date(self):
        from employees.automation import notify_probation_result_if_needed

        employee = self._employee('NV7')
        notify_probation_result_if_needed(employee, 'failed', datetime.date(2026, 8, 15))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Không đạt', mail.outbox[0].body)

    @patch('employees.services._notify_probation_result_safe')
    def test_recompute_final_result_calls_notify_only_on_became_pass(self, mock_notify):
        from employees.services import recompute_final_result

        employee = Employee.objects.create(
            tenant=self.tenant, code='NV8', name='G', restaurant=self.restaurant, position='NV Phục vụ',
            is_legacy=True,  # grandfather -> 'Pass thu viec' ngay lan dau (became_pass=True)
        )
        recompute_final_result(employee)
        mock_notify.assert_called_once_with(employee, 'pass', employee.pass_date)
        recompute_final_result(employee)  # goi lai - final_result khong doi -> KHONG goi them
        recompute_final_result(employee)
        mock_notify.assert_called_once()

    @patch('employees.services._notify_probation_result_safe')
    def test_change_employee_status_resigned_during_probation_calls_notify_failed(self, mock_notify):
        employee = Employee.objects.create(
            tenant=self.tenant, code='NV9', name='H', restaurant=self.restaurant, position='NV Phục vụ',
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        change_employee_status(employee, 'resigned')
        mock_notify.assert_any_call(employee, 'failed', employee.resigned_at)

    @patch('employees.services._notify_probation_result_safe')
    def test_resigning_after_already_active_does_not_call_failed(self, mock_notify):
        employee = Employee.objects.create(
            tenant=self.tenant, code='NV10', name='I', restaurant=self.restaurant, position='NV Phục vụ',
            employee_status=Employee.EmployeeStatus.ACTIVE,
        )
        change_employee_status(employee, 'resigned')
        failed_calls = [c for c in mock_notify.call_args_list if c.args[1] == 'failed']
        self.assertEqual(failed_calls, [])


class ProbationReminderTargetsTests(TestCase):
    """Nhom 3C (Prompt_Nhom3C_NhacViec_TrongApp.md muc 2): probation_reminder_targets - LUON gom
    QLNH; THEM Bep truong neu nhan su thuoc khoi bep (BOH); KHONG gui cho toan bo bql cua nha
    hang (vd Giam sat/Bep pho khong lien quan khong duoc nhan)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='Nhà hàng 1')
        self.other_restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH2', name='Nhà hàng 2')
        self.qlnh = User.objects.create_user(
            username='qlnh1', password='x', tenant=self.tenant, role=User.Role.BQL,
            job_title=User.JobTitle.QLNH, restaurant=self.restaurant,
        )
        self.bep_truong = User.objects.create_user(
            username='bt1', password='x', tenant=self.tenant, role=User.Role.BQL,
            job_title=User.JobTitle.BEP_TRUONG, restaurant=self.restaurant,
        )
        self.giam_sat = User.objects.create_user(
            username='gs1', password='x', tenant=self.tenant, role=User.Role.BQL,
            job_title=User.JobTitle.GIAM_SAT, restaurant=self.restaurant,
        )
        # QLNH nha hang KHAC - khong duoc nhan cho nhan su cua nha hang nay.
        User.objects.create_user(
            username='qlnh2', password='x', tenant=self.tenant, role=User.Role.BQL,
            job_title=User.JobTitle.QLNH, restaurant=self.other_restaurant,
        )

    def test_foh_employee_gets_only_qlnh(self):
        from employees.automation import probation_reminder_targets

        employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='Phục vụ A', position='NV Phục vụ', restaurant=self.restaurant,
        )
        targets = probation_reminder_targets(employee)
        self.assertEqual(set(targets), {self.qlnh})

    def test_boh_employee_gets_qlnh_and_bep_truong(self):
        from employees.automation import probation_reminder_targets

        employee = Employee.objects.create(
            tenant=self.tenant, code='NV2', name='Bếp A', position='Phụ bếp', restaurant=self.restaurant,
        )
        targets = probation_reminder_targets(employee)
        self.assertEqual(set(targets), {self.qlnh, self.bep_truong})

    def test_no_restaurant_returns_empty(self):
        from employees.automation import probation_reminder_targets

        employee = Employee.objects.create(tenant=self.tenant, code='NV3', name='Không NH', position='NV Phục vụ')
        self.assertEqual(probation_reminder_targets(employee), [])


class ProbationRemindersTests(TestCase):
    """Nhom 3C luong 6: check_probation_reminders - 2 dieu kien doc lap + chong spam
    (remind_repeat_days) + tat cong tac / nhan su cu khong bi cuon vao."""

    def setUp(self):
        from employees.models import AutomationSettings

        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='Nhà hàng 1')
        self.qlnh = User.objects.create_user(
            username='qlnh1', password='x', email='qlnh1@example.com', tenant=self.tenant,
            role=User.Role.BQL, job_title=User.JobTitle.QLNH, restaurant=self.restaurant,
        )
        self.settings_obj = AutomationSettings.objects.create(
            tenant=self.tenant, remind_managers=True, remind_untrained_after_days=3,
            remind_days_before_deadline=3, remind_repeat_days=3,
        )

    def _employee(self, code, **kwargs):
        defaults = dict(
            tenant=self.tenant, code=code, name=f'NV {code}', restaurant=self.restaurant,
            position='NV Phục vụ', is_legacy=False, employee_status=Employee.EmployeeStatus.PROBATION,
        )
        defaults.update(kwargs)
        return Employee.objects.create(**defaults)

    @patch('employees.services.checklist_progress_percent', return_value=0)
    def test_untrained_reminder_sent_to_qlnh(self, mock_progress):
        from sourcing.models import Notification

        employee = self._employee('NV1', start_date=datetime.date.today() - datetime.timedelta(days=5))
        sent = check_probation_reminders_helper(employee)
        self.assertIn('probation_untrained', sent)
        self.assertTrue(Notification.objects.filter(user=self.qlnh, category='probation_untrained').exists())

    @patch('employees.services.checklist_progress_percent', return_value=0)
    def test_untrained_not_yet_reached_threshold_days(self, mock_progress):
        employee = self._employee('NV2', start_date=datetime.date.today() - datetime.timedelta(days=1))
        sent = check_probation_reminders_helper(employee)
        self.assertEqual(sent, [])

    @patch('employees.services.checklist_progress_percent', return_value=100)
    def test_untrained_not_sent_when_checklist_complete(self, mock_progress):
        employee = self._employee('NV3', start_date=datetime.date.today() - datetime.timedelta(days=10))
        sent = check_probation_reminders_helper(employee)
        self.assertEqual(sent, [])

    def test_deadline_reminder_sent_when_within_threshold(self):
        employee = self._employee(
            'NV4', start_date=datetime.date.today() - datetime.timedelta(days=13), probation_days=15,
        )
        # days_left = 15 - 13 = 2 <= nguong 3 va > 0.
        sent = check_probation_reminders_helper(employee)
        self.assertIn('probation_deadline', sent)

    def test_deadline_not_sent_when_already_overdue(self):
        employee = self._employee(
            'NV5', start_date=datetime.date.today() - datetime.timedelta(days=20), probation_days=15,
        )
        # days_left am (qua han) - khong thuoc pham vi "sap den han" cua luong nhac nay.
        sent = check_probation_reminders_helper(employee)
        self.assertNotIn('probation_deadline', sent)

    @patch('employees.services.checklist_progress_percent', return_value=0)
    def test_no_duplicate_within_repeat_days(self, mock_progress):
        employee = self._employee('NV6', start_date=datetime.date.today() - datetime.timedelta(days=5))
        first = check_probation_reminders_helper(employee)
        second = check_probation_reminders_helper(employee)
        self.assertIn('probation_untrained', first)
        self.assertEqual(second, [])

    @patch('employees.services.checklist_progress_percent', return_value=0)
    def test_resend_after_repeat_days_elapsed(self, mock_progress):
        from employees.models import ProbationReminderLog

        employee = self._employee('NV7', start_date=datetime.date.today() - datetime.timedelta(days=5))
        check_probation_reminders_helper(employee)
        log = ProbationReminderLog.objects.get(employee=employee, category='probation_untrained')
        # .update() (khong phai .save()) de bo qua auto_now - auto_now se GHI DE ve "bay gio"
        # moi lan save(), khong the lui ngay qua instance.save() thong thuong.
        ProbationReminderLog.objects.filter(pk=log.pk).update(
            last_sent_at=timezone.now() - datetime.timedelta(days=4),
        )
        second = check_probation_reminders_helper(employee)
        self.assertIn('probation_untrained', second)

    @patch('employees.services.checklist_progress_percent', return_value=0)
    def test_toggle_off_sends_nothing(self, mock_progress):
        self.settings_obj.remind_managers = False
        self.settings_obj.save(update_fields=['remind_managers'])
        employee = self._employee('NV8', start_date=datetime.date.today() - datetime.timedelta(days=5))
        sent = check_probation_reminders_helper(employee)
        self.assertEqual(sent, [])

    @patch('employees.services.checklist_progress_percent', return_value=0)
    def test_legacy_employee_not_reminded(self, mock_progress):
        employee = self._employee(
            'NV9', start_date=datetime.date.today() - datetime.timedelta(days=5), is_legacy=True,
        )
        sent = check_probation_reminders_helper(employee)
        self.assertEqual(sent, [])

    @patch('employees.services.checklist_progress_percent', return_value=0)
    def test_boh_employee_also_notifies_bep_truong(self, mock_progress):
        from sourcing.models import Notification

        bep_truong = User.objects.create_user(
            username='bt1', password='x', tenant=self.tenant, role=User.Role.BQL,
            job_title=User.JobTitle.BEP_TRUONG, restaurant=self.restaurant,
        )
        employee = self._employee(
            'NV10', position='Phụ bếp', start_date=datetime.date.today() - datetime.timedelta(days=5),
        )
        check_probation_reminders_helper(employee)
        self.assertTrue(Notification.objects.filter(user=bep_truong, category='probation_untrained').exists())
        self.assertTrue(Notification.objects.filter(user=self.qlnh, category='probation_untrained').exists())


def check_probation_reminders_helper(employee):
    from employees.automation import check_probation_reminders

    return check_probation_reminders(employee)


class RemindManagersProbationCommandTests(TestCase):
    """Nhom 3C muc 3: management command remind_managers_probation - quet toan bo tenant, chi
    xu ly tenant bat remind_managers, ghi nhan qua Notification (chuong NotificationsBell)."""

    def setUp(self):
        from employees.models import AutomationSettings

        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='Nhà hàng 1')
        self.qlnh = User.objects.create_user(
            username='qlnh1', password='x', tenant=self.tenant, role=User.Role.BQL,
            job_title=User.JobTitle.QLNH, restaurant=self.restaurant,
        )
        AutomationSettings.objects.create(tenant=self.tenant, remind_managers=True)
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', position='NV Phục vụ', restaurant=self.restaurant,
            is_legacy=False, employee_status=Employee.EmployeeStatus.PROBATION,
            start_date=datetime.date.today() - datetime.timedelta(days=10),
        )

    @patch('employees.services.checklist_progress_percent', return_value=0)
    def test_command_creates_notification_for_untrained_employee(self, mock_progress):
        from sourcing.models import Notification

        call_command('remind_managers_probation')
        self.assertTrue(Notification.objects.filter(user=self.qlnh, category='probation_untrained').exists())

    def test_command_runs_with_no_matching_employees(self):
        """Kiem thu 'chay thu command' - khong loi du khong co nhan su nao khop dieu kien."""
        Employee.objects.all().delete()
        call_command('remind_managers_probation')  # khong duoc raise


class EmployeeListRouterShadowingRegressionTests(TestCase):
    """Prompt_Fix_TrangTrang_MapUndefined.md - hoi quy CHINH XAC cho nguyen nhan goc gay trang
    man /employees: employees/urls.py tung dung 2 DefaultRouter() (router cho EmployeeViewSet +
    automation_router cho onboarding-course-rules/probation-exam-rules). DefaultRouter TU SINH
    THEM 1 "API root view" rieng tai pattern '^$' cho MOI instance - vi automation_router.urls
    dat TRUOC router.urls trong urlpatterns, root view RONG cua automation_router (chi liet ke 2
    endpoint cua no) KHOP TRUOC va NUOT MAT list-view that su cua EmployeeViewSet (cung o pattern
    '^$' do router.register('', ...) - prefix rong). Hau qua: GET /api/employees/ tra ve
    {"onboarding-course-rules": "...", "probation-exam-rules": "..."} thay vi {count, results}.

    QUAN TRONG: cac test khac trong file nay dung reverse('employee-list') de dung URL - reverse()
    chi tra cuu TEN -> pattern, KHONG mo phong THU TU thuc su Django dung de resolve 1 request
    that (nen KHONG bao gio phat hien duoc loi nay du hang tram test dung reverse() da pass). Test
    nay dung DUNG DUONG DAN CHUOI ('/api/employees/'), giong browser/axios thuc su goi, de dam
    bao khong bao gio tai dien loai loi nay ma khong bi bat."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', is_legacy=False)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def test_root_employees_path_returns_paginated_employee_list_not_router_index(self):
        resp = self.client.get('/api/employees/', {'page_size': 20})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('results', resp.data)
        self.assertIn('count', resp.data)
        self.assertIsInstance(resp.data['results'], list)
        self.assertEqual(resp.data['results'][0]['code'], 'NV1')
        # Dung y - day chinh la bug that: root view cua automation_router se tra ve dict co
        # 2 key nay THAY VI {count, results}.
        self.assertNotIn('onboarding-course-rules', resp.data)
        self.assertNotIn('probation-exam-rules', resp.data)

    def test_root_employees_path_with_list_tab_matches_employee_list_view_name(self):
        resp = self.client.get('/api/employees/', {'list_tab': 'new', 'page_size': 20})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('results', resp.data)

    def test_sibling_automation_endpoints_still_reachable_after_fix(self):
        """Dam bao khong sua qua tay - 2 endpoint cua automation_router van hoat dong binh
        thuong (chi khong con che mat EmployeeViewSet nua)."""
        resp1 = self.client.get('/api/employees/onboarding-course-rules/')
        self.assertEqual(resp1.status_code, 200)
        self.assertIn('results', resp1.data)
        resp2 = self.client.get('/api/employees/probation-exam-rules/')
        self.assertEqual(resp2.status_code, 200)
        self.assertIn('results', resp2.data)


class PositionCatalogTests(TestCase):
    """Muc 16 Phase 1 phan A (Prompt_Muc16_Phase1_ViTri_CauHinhMenu.md) - CRUD danh muc Vi tri
    chuc danh (PositionViewSet, prefix 'positions-catalog/') + PositionListView doc tu danh muc
    khi da co, fallback ve chuoi distinct khi rong."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client = APIClient()

    def test_any_authenticated_role_can_list(self):
        Position.objects.create(tenant=self.tenant, name='Phục vụ')
        self.client.force_authenticate(self.trainer)
        resp = self.client.get('/api/employees/positions-catalog/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'][0]['name'], 'Phục vụ')

    def test_non_admin_cannot_create(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post('/api/employees/positions-catalog/', {'name': 'Phục vụ'})
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_create_and_duplicate_name_is_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/employees/positions-catalog/', {'name': 'Phục vụ'})
        self.assertEqual(resp.status_code, 201)
        dup = self.client.post('/api/employees/positions-catalog/', {'name': 'phục vụ'})
        self.assertEqual(dup.status_code, 400)

    def test_admin_can_hide_and_edit_position(self):
        pos = Position.objects.create(tenant=self.tenant, name='Phục vụ')
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(f'/api/employees/positions-catalog/{pos.id}/', {'is_active': False})
        self.assertEqual(resp.status_code, 200)
        pos.refresh_from_db()
        self.assertFalse(pos.is_active)

    def test_position_list_view_reads_active_catalog_ordered(self):
        Position.objects.create(tenant=self.tenant, name='Bếp phó', order=2)
        Position.objects.create(tenant=self.tenant, name='Phục vụ', order=1)
        Position.objects.create(tenant=self.tenant, name='Nghỉ dùng', order=0, is_active=False)
        self.client.force_authenticate(self.trainer)
        resp = self.client.get('/api/employees/positions/')
        self.assertEqual(resp.data, ['Phục vụ', 'Bếp phó'])

    def test_position_list_view_falls_back_when_catalog_empty(self):
        Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', position='Bếp trưởng')
        self.client.force_authenticate(self.trainer)
        resp = self.client.get('/api/employees/positions/')
        self.assertIn('Bếp trưởng', resp.data)
        self.assertIn('Quản lý nhà hàng', resp.data)  # vi tri cap O chuan van con trong fallback


class PrerequisiteStatusCurriculumTests(TestCase):
    """Khung noi dung cap O - Buoc 1 (Prompt_KhungNoiDung_CapO_Buoc1.md muc 3) -
    prerequisite_status doc CurriculumItem khi vi tri tien quyet DA cau hinh, fallback ve
    GS/BP_CONTENT_TOPICS hardcode khi CHUA cau hinh (khong doi hanh vi)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_falls_back_to_hardcode_when_position_not_configured(self):
        # 'QL' can noi dung 'GS' - giam_sat CHUA co CurriculumItem nao -> dung GS_CONTENT_TOPICS.
        result = prerequisite_status(self.tenant, 'QL', ['Kỹ năng đào tạo'], {})
        content_item = next(i for i in result['items'] if i['label'] == 'Hoàn thành nội dung GS')
        self.assertFalse(content_item['ok'])
        self.assertIn('VSATTP', content_item['missing'])

    def test_reads_from_configured_curriculum_instead_of_hardcode(self):
        doc = Document.objects.create(tenant=self.tenant, name='Kỹ năng riêng', file_url='https://x/doc.pdf')
        CurriculumItem.objects.create(tenant=self.tenant, position='giam_sat', document=doc)

        # Da hoc dung 1 noi dung duy nhat trong khung moi (khac han GS_CONTENT_TOPICS hardcode).
        result_done = prerequisite_status(self.tenant, 'QL', ['Kỹ năng đào tạo', 'Kỹ năng riêng'], {})
        content_item = next(i for i in result_done['items'] if i['label'] == 'Hoàn thành nội dung GS')
        self.assertTrue(content_item['ok'])
        self.assertEqual(content_item['missing'], [])

        # Chua hoc noi dung khung moi (nhung co du GS_CONTENT_TOPICS cu) -> van thieu, vi khung
        # cau hinh la nguon duy nhat khi DA cau hinh (khong con doi chieu voi hardcode nua).
        result_not_done = prerequisite_status(
            self.tenant, 'QL', sorted({'Kỹ năng đào tạo'} | {'Xử lý tình huống', 'Kỹ năng mềm', 'VSATTP', 'Kỹ năng Office', 'Dinh dưỡng', 'Vận hành'}), {},
        )
        content_item2 = next(i for i in result_not_done['items'] if i['label'] == 'Hoàn thành nội dung GS')
        self.assertFalse(content_item2['ok'])
        self.assertEqual(content_item2['missing'], ['Kỹ năng riêng'])

    def test_btr_target_reads_bep_pho_curriculum(self):
        doc = Document.objects.create(tenant=self.tenant, name='Quản lý bếp', file_url='https://x/doc.pdf')
        CurriculumItem.objects.create(tenant=self.tenant, position='bep_pho', document=doc)
        result = prerequisite_status(self.tenant, 'BTr', ['Kỹ năng đào tạo', 'Quản lý bếp'], {})
        content_item = next(i for i in result['items'] if i['label'] == 'Hoàn thành nội dung BP')
        self.assertTrue(content_item['ok'])


class CurriculumItemApiTests(TestCase):
    """Khung noi dung cap O - Buoc 1 (Prompt_KhungNoiDung_CapO_Buoc1.md muc 2)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.doc1 = Document.objects.create(tenant=self.tenant, name='VSATTP', file_url='https://x/1.pdf')
        self.doc2 = Document.objects.create(tenant=self.tenant, name='Sự cố', file_url='https://x/2.pdf')
        self.client = APIClient()

    def test_om_can_read_but_trainer_cannot(self):
        CurriculumItem.objects.create(tenant=self.tenant, position='giam_sat', document=self.doc1)
        self.client.force_authenticate(self.om)
        resp = self.client.get('/api/curriculum/', {'position': 'giam_sat'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['results'][0]['document_name'], 'VSATTP')

        self.client.force_authenticate(self.trainer)
        resp2 = self.client.get('/api/curriculum/')
        self.assertEqual(resp2.status_code, 403)

    def test_om_cannot_write(self):
        self.client.force_authenticate(self.om)
        resp = self.client.post('/api/curriculum/', {'position': 'giam_sat', 'document': self.doc1.id})
        self.assertEqual(resp.status_code, 403)

    def test_admin_create_rejects_invalid_position(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/curriculum/', {'position': 'bep_truong_phu', 'document': self.doc1.id})
        self.assertEqual(resp.status_code, 400)

    def test_admin_create_rejects_duplicate(self):
        self.client.force_authenticate(self.admin)
        self.client.post('/api/curriculum/', {'position': 'giam_sat', 'document': self.doc1.id})
        dup = self.client.post('/api/curriculum/', {'position': 'giam_sat', 'document': self.doc1.id})
        self.assertEqual(dup.status_code, 400)

    def test_bulk_assign_creates_for_each_position_and_marks_shared(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/curriculum/bulk/', {
            'document_ids': [self.doc1.id, self.doc2.id],
            'positions': ['giam_sat', 'qlnh'],
            'is_shared': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['created'], 4)
        rows = CurriculumItem.objects.filter(tenant=self.tenant)
        self.assertEqual(rows.count(), 4)
        self.assertTrue(all(r.is_shared for r in rows))

    def test_bulk_assign_is_idempotent_skips_existing(self):
        CurriculumItem.objects.create(tenant=self.tenant, position='giam_sat', document=self.doc1)
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/curriculum/bulk/', {
            'document_ids': [self.doc1.id], 'positions': ['giam_sat'], 'is_shared': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(CurriculumItem.objects.count(), 1)

    def test_bulk_assign_rejects_invalid_position(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/curriculum/bulk/', {
            'document_ids': [self.doc1.id], 'positions': ['ceo'],
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_cannot_bulk_assign(self):
        self.client.force_authenticate(self.om)
        resp = self.client.post('/api/curriculum/bulk/', {
            'document_ids': [self.doc1.id], 'positions': ['giam_sat'],
        }, format='json')
        self.assertEqual(resp.status_code, 403)


# ==================================================================== Khung noi dung cap S -
# Buoc 2 (Prompt_KhungNoiDung_CapS_Buoc2.md). BAT BUOC co regression day du: khi CHUA phan loai
# checklist (moi muc = 'core' mac dinh), moi ket qua nghiep vu (dat thu viec, dang ky/len level,
# du dieu kien thi thu viec) phai GIONG HET truoc day.

class ChecklistProgressByPhaseTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', position='Phục vụ', restaurant=self.restaurant,
        )

    def _checklist(self, task_name, phase='core'):
        return Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name=task_name, phase=phase,
        )

    def test_no_checklist_for_position_is_vacuously_satisfied(self):
        stats = checklist_progress_by_phase(self.employee)
        self.assertEqual(stats, {'core_done': 0, 'core_total': 0, 'core_pct': 100, 'full_done': 0, 'full_total': 0, 'full_pct': 0})

    def test_unclassified_checklist_core_pct_equals_full_pct(self):
        c1 = self._checklist('Việc 1')
        self._checklist('Việc 2')
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=c1, status=TrainingProgress.Status.DONE)
        stats = checklist_progress_by_phase(self.employee)
        self.assertEqual(stats['full_total'], 2)
        self.assertEqual(stats['core_total'], 2)  # moi muc deu la core mac dinh
        self.assertEqual(stats['core_pct'], stats['full_pct'])
        self.assertEqual(stats['full_pct'], 50)

    def test_classified_core_and_completion_tracked_separately(self):
        core1 = self._checklist('Core 1', phase='core')
        self._checklist('Core 2', phase='core')
        self._checklist('Completion 1', phase='completion')
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=core1, status=TrainingProgress.Status.DONE)
        stats = checklist_progress_by_phase(self.employee)
        self.assertEqual(stats['core_total'], 2)
        self.assertEqual(stats['core_done'], 1)
        self.assertEqual(stats['core_pct'], 50)
        self.assertEqual(stats['full_total'], 3)
        self.assertEqual(stats['full_pct'], 33)

    def test_legacy_employee_shortcut_unchanged(self):
        legacy = Employee.objects.create(tenant=self.tenant, code='NVCU', name='Cũ', is_legacy=True)
        stats = checklist_progress_by_phase(legacy)
        self.assertEqual(stats['core_pct'], 100)
        self.assertEqual(stats['full_pct'], 100)


class ProbationChecklistOkTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', position='Phục vụ', restaurant=self.restaurant,
        )

    def _checklist(self, task_name, phase='core'):
        return Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name=task_name, phase=phase,
        )

    def test_default_has_probation_true_unclassified_needs_full_100(self):
        c1 = self._checklist('Việc 1')
        self._checklist('Việc 2')
        # 1/2 chua xong -> khong dat, dung y "100% toan bo" cu (moi muc deu la core mac dinh).
        self.assertFalse(probation_checklist_ok(self.employee))
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=c1, status=TrainingProgress.Status.DONE)
        self.assertFalse(probation_checklist_ok(self.employee))  # 1/2 - van chua du 100%

    def test_classified_position_only_needs_core_done(self):
        core1 = self._checklist('Core 1', phase='core')
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=core1, status=TrainingProgress.Status.DONE)
        self._checklist('Completion 1', phase='completion')  # CHUA lam, khong quan trong voi core
        self.assertTrue(probation_checklist_ok(self.employee))

    def test_has_probation_false_always_ok_regardless_of_checklist(self):
        self._checklist('Việc 1')  # 0% - se FAIL neu has_probation=True
        update_grading_config(self.tenant, None, {'has_probation': False})
        self.assertTrue(probation_checklist_ok(self.employee))


class ComputeFinalResultRegressionTests(TestCase):
    """BAT BUOC: khi CHUA phan loai checklist, ket qua dat/khong dat thu viec phai GIONG HET
    truoc day (Prompt_KhungNoiDung_CapS_Buoc2.md, phan 'Backward-compat & regression')."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', position='Phục vụ', restaurant=self.restaurant,
            operation_unit=Employee.OperationUnit.RESTAURANT, skill_score=Decimal('0.90'),
        )
        self.checklist = Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name='Việc 1',
        )

    def _mark_checklist_done(self):
        TrainingProgress.objects.create(
            tenant=self.tenant, employee=self.employee, checklist=self.checklist, status=TrainingProgress.Status.DONE,
        )

    def test_unclassified_all_conditions_met_passes_same_as_before(self):
        self._mark_checklist_done()
        with patch('employees.services.lms_done', return_value=True), \
             patch('employees.services.exam_pass', return_value=True):
            self.assertEqual(compute_final_result(self.employee), 'Pass thử việc')

    def test_unclassified_checklist_not_done_fails_same_as_before(self):
        # checklist con 1 muc chua Hoan thanh -> 0%
        with patch('employees.services.lms_done', return_value=True), \
             patch('employees.services.exam_pass', return_value=True):
            self.assertEqual(compute_final_result(self.employee), 'Tiếp tục thử việc')

    def test_has_probation_false_bypasses_checklist_gate_only(self):
        update_grading_config(self.tenant, None, {'has_probation': False})
        # checklist VAN chua xong (0%), nhung has_probation=False -> bo qua rieng dieu kien nay.
        with patch('employees.services.lms_done', return_value=True), \
             patch('employees.services.exam_pass', return_value=True):
            self.assertEqual(compute_final_result(self.employee), 'Pass thử việc')

    def test_has_probation_false_still_requires_other_conditions(self):
        update_grading_config(self.tenant, None, {'has_probation': False})
        # LMS chua xong -> van "Tiep tuc thu viec" du checklist gate da bo qua.
        with patch('employees.services.lms_done', return_value=False), \
             patch('employees.services.exam_pass', return_value=True):
            self.assertEqual(compute_final_result(self.employee), 'Tiếp tục thử việc')


class RegistrationStatusSequentialGateTests(TestCase):
    """Cong 2 - Buoc 2 muc 5. BAT BUOC regression: chua phan loai gi -> dang ky vi tri ke KHONG
    bi chan boi checklist (dung hanh vi cu, chi co dieu kien 3 thang + khong co dot mo)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.employee = Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', position='Phục vụ', restaurant=self.restaurant,
            job_level='S1.1', start_date=timezone.now().date() - datetime.timedelta(days=200),
        )

    def _checklist(self, task_name, phase='core'):
        return Checklist.objects.create(
            tenant=self.tenant, brand='Kampong', position='Phục vụ', task_name=task_name, phase=phase,
        )

    def test_regression_no_classification_registration_not_blocked_by_checklist(self):
        # Checklist con do dang (0% - truoc day KHONG co dieu kien checklist o registration_status).
        self._checklist('Việc 1')
        status = registration_status(self.employee)
        self.assertTrue(status['can'])
        self.assertEqual(status['reason'], '')

    def test_regression_no_checklist_at_all_registration_not_blocked(self):
        status = registration_status(self.employee)
        self.assertTrue(status['can'])

    def test_classified_position_blocks_until_full_100_percent(self):
        core1 = self._checklist('Core 1', phase='core')
        self._checklist('Completion 1', phase='completion')
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=core1, status=TrainingProgress.Status.DONE)
        # Core xong (100%) nhung completion CHUA -> full < 100% -> bi chan dang ky vi tri ke.
        status = registration_status(self.employee)
        self.assertFalse(status['can'])
        self.assertEqual(status['reason'], 'Chưa hoàn thiện toàn bộ nội dung vị trí hiện tại.')

    def test_classified_position_allows_when_full_100_percent(self):
        core1 = self._checklist('Core 1', phase='core')
        completion1 = self._checklist('Completion 1', phase='completion')
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=core1, status=TrainingProgress.Status.DONE)
        TrainingProgress.objects.create(tenant=self.tenant, employee=self.employee, checklist=completion1, status=TrainingProgress.Status.DONE)
        status = registration_status(self.employee)
        self.assertTrue(status['can'])

    def test_sequential_positions_false_disables_gate(self):
        self._checklist('Core 1', phase='core')
        self._checklist('Completion 1', phase='completion')  # 0% full, se chan neu con bat
        update_grading_config(self.tenant, None, {'sequential_positions': False})
        status = registration_status(self.employee)
        self.assertTrue(status['can'])


class ChecklistBulkAssignPhaseApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.om = User.objects.create_user(username='om1', password='x', tenant=self.tenant, role='om')
        self.c1 = Checklist.objects.create(tenant=self.tenant, task_name='Việc 1', category='Nhóm A')
        self.c2 = Checklist.objects.create(tenant=self.tenant, task_name='Việc 2', category='Nhóm A')
        self.client = APIClient()

    def test_admin_bulk_assign_by_ids(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/checklist/bulk-assign-phase/', {
            'ids': [self.c1.id, self.c2.id], 'phase': 'completion',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['updated'], 2)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.phase, 'completion')

    def test_admin_bulk_assign_by_category(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/checklist/bulk-assign-phase/', {
            'category': 'Nhóm A', 'phase': 'completion',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['updated'], 2)

    def test_invalid_phase_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/checklist/bulk-assign-phase/', {
            'ids': [self.c1.id], 'phase': 'invalid',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_non_admin_cannot_bulk_assign_phase(self):
        self.client.force_authenticate(self.om)
        resp = self.client.post('/api/checklist/bulk-assign-phase/', {
            'ids': [self.c1.id], 'phase': 'completion',
        }, format='json')
        self.assertEqual(resp.status_code, 403)


class GradingConfigNewFieldsTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()

    def test_defaults_match_current_behavior(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get('/api/settings/grading/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['has_probation'])
        self.assertTrue(resp.data['sequential_positions'])
        self.assertEqual(resp.data['probation_window_days'], 15)
        self.assertEqual(resp.data['roadmap_window_days'], 90)

    def test_put_updates_and_logs_history(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.put('/api/settings/grading/', {
            'has_probation': False, 'sequential_positions': False,
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['has_probation'])
        self.assertFalse(resp.data['sequential_positions'])

        history = self.client.get('/api/settings/grading/history/')
        fields_changed = {row['field'] for row in history.data}
        self.assertIn('has_probation', fields_changed)
        self.assertIn('sequential_positions', fields_changed)
