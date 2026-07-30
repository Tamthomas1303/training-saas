import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from cls_sync.models import ExamResult
from employees.models import Employee

from .metrics_csv import _is_assigned_status, _is_attended_status, service_audit_block, training_org_block
from .metrics_training import exam_block, new_hires_block
from .period import compute_period, previous_period


class PeriodTests(TestCase):
    def test_week_is_monday_to_sunday(self):
        # 2026-07-30 la thu Nam (Thursday)
        start, end, label = compute_period('week', datetime.date(2026, 7, 30))
        self.assertEqual(start, datetime.date(2026, 7, 27))  # Monday
        self.assertEqual(end, datetime.date(2026, 7, 30))    # capped o ref_date (chua het CN)
        self.assertIn('Tuần', label)

    def test_month_capped_at_ref_date(self):
        start, end, _ = compute_period('month', datetime.date(2026, 7, 10))
        self.assertEqual(start, datetime.date(2026, 7, 1))
        self.assertEqual(end, datetime.date(2026, 7, 10))

    def test_previous_week(self):
        start, _, _ = compute_period('week', datetime.date(2026, 7, 30))
        prev_start, prev_end = previous_period('week', start)
        self.assertEqual(prev_start, datetime.date(2026, 7, 20))
        self.assertEqual(prev_end, datetime.date(2026, 7, 26))


class NewHiresBlockTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_counts_within_period(self):
        Employee.objects.create(
            tenant=self.tenant, code='NV1', name='A', start_date=datetime.date(2026, 7, 5),
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        Employee.objects.create(
            tenant=self.tenant, code='NV2', name='B', start_date=datetime.date(2026, 6, 1),
            employee_status=Employee.EmployeeStatus.PROBATION,
        )
        resigned = Employee.objects.create(
            tenant=self.tenant, code='NV3', name='C', start_date=datetime.date(2026, 6, 1),
            employee_status=Employee.EmployeeStatus.RESIGNED, resigned_at=datetime.date(2026, 7, 10),
        )
        passed = Employee.objects.create(
            tenant=self.tenant, code='NV4', name='D', start_date=datetime.date(2026, 6, 1),
            pass_date=datetime.date(2026, 7, 15), final_result='Pass thử việc',
        )
        start, end = datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)
        result = new_hires_block(self.tenant, start, end, datetime.date(2026, 7, 31))
        self.assertEqual(result['total_new_hires'], 1)  # chi NV1 (start_date trong ky, dang lam)
        self.assertEqual(result['resigned_count'], 1)
        self.assertEqual(result['passed_count'], 1)
        self.assertTrue(Employee.objects.filter(pk=resigned.pk).exists())
        self.assertTrue(Employee.objects.filter(pk=passed.pk).exists())


class ExamBlockTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='A')

    def test_classification_and_prefers_final_score(self):
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=1,
            score=Decimal('65.00'), score_adjusted=Decimal('92.00'),
            exam_date=datetime.date(2026, 7, 10),
        )
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='15N', attempt=2,
            score=Decimal('82.00'), exam_date=datetime.date(2026, 7, 15),
        )
        # ngoai ky - khong duoc tinh
        ExamResult.objects.create(
            tenant=self.tenant, employee=self.employee, exam_name='30N', attempt=1,
            score=Decimal('50.00'), exam_date=datetime.date(2026, 8, 1),
        )
        result = exam_block(self.tenant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))
        self.assertEqual(result['total_attempts'], 2)
        self.assertEqual(result['distinct_people'], 1)
        self.assertEqual(result['pass_rate'], 100.0)
        xs = next(c for c in result['classification'] if c['key'] == 'xuat_sac')
        self.assertEqual(xs['count'], 1)  # diem 92 (final_score, uu tien adjusted)
        tb = next(c for c in result['classification'] if c['key'] == 'trung_binh')
        self.assertEqual(tb['count'], 1)  # diem 82


class CsvStatusHeuristicTests(TestCase):
    def test_assigned_status(self):
        self.assertTrue(_is_assigned_status('Đã gán'))
        self.assertTrue(_is_assigned_status(''))
        self.assertFalse(_is_assigned_status('Đã huỷ'))

    def test_attended_status(self):
        self.assertTrue(_is_attended_status('Đã tham gia'))
        self.assertFalse(_is_attended_status('Chưa tham gia'))
        self.assertFalse(_is_attended_status(''))


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.encoding = None

    def raise_for_status(self):
        pass


class TrainingOrgCsvTests(TestCase):
    @patch('reports.metrics_csv.requests.get')
    def test_training_org_block(self, mock_get):
        csv_text = (
            'Training_Date,Employee_ID,Employee_Name,Cousera_Code,Cousera_Name,Class_Code,'
            'Learner_Group,Assignment_Status,Participation_Status,Training_Month\n'
            '05/07/2026,NV1,A,C1,Lop Pha che,C1,G1,Đã gán,Đã tham gia,07/2026\n'
            '06/07/2026,NV2,B,C1,Lop Pha che,C1,G1,Đã gán,Chưa tham gia,07/2026\n'
            '01/08/2026,NV3,C,C1,Lop Pha che,C1,G1,Đã gán,Đã tham gia,08/2026\n'
        )
        mock_get.return_value = FakeResponse(csv_text)
        result = training_org_block('http://fake-url', datetime.date(2026, 7, 1), datetime.date(2026, 7, 31))
        self.assertEqual(result['total_classes'], 1)
        self.assertEqual(result['total_assigned'], 2)
        self.assertEqual(result['total_attended'], 1)
        self.assertEqual(result['overall_rate'], 50.0)

    def test_returns_none_when_no_url(self):
        self.assertIsNone(training_org_block('', datetime.date(2026, 7, 1), datetime.date(2026, 7, 31)))


class ServiceAuditCsvTests(TestCase):
    @patch('reports.metrics_csv.requests.get')
    def test_service_audit_block(self, mock_get):
        # A..O = 15 cot; D=idx3 ngay, F=idx5 nha hang, I=idx8 Score_Criteria, J=idx9 Criteria,
        # N=idx13 Result_Score, O=idx14 Department_Name.
        header = ','.join(['col'] * 15)

        def row(date_, restaurant, score_criteria, criteria, result_score, dept):
            cells = ['x'] * 15
            cells[3] = date_
            cells[5] = restaurant
            cells[8] = str(score_criteria)
            cells[9] = criteria
            cells[13] = str(result_score)
            cells[14] = dept
            return ','.join(cells)

        csv_text = '\n'.join([
            header,
            row('05/07/2026', 'NH A', 10, 'Ve sinh', 10, 'Phòng Đào tạo'),
            row('06/07/2026', 'NH A', 10, 'Thai do', 0, 'Phòng Đào tạo'),
            row('07/07/2026', 'NH B', 10, 'Thai do', 0, 'Phòng Đào tạo'),
            row('08/07/2026', 'NH B', 10, 'Ve sinh', 5, 'Phòng Nhân sự'),  # khac phong ban - loai
        ])
        mock_get.return_value = FakeResponse(csv_text)
        result = service_audit_block('http://fake-url', datetime.date(2026, 7, 1), datetime.date(2026, 7, 31), 'week')
        by_name = {r['restaurant']: r['score'] for r in result['restaurants']}
        self.assertEqual(by_name['NH A'], 50.0)  # (10+0)/(10+10)
        self.assertEqual(by_name['NH B'], 0.0)   # 0/10 (dong Phong Nhan su bi loai)
        self.assertEqual(len(result['top_problems']), 1)
        self.assertEqual(result['top_problems'][0]['criteria'], 'Thai do')
        self.assertEqual(result['top_problems'][0]['count'], 2)

    def test_returns_none_when_no_url(self):
        self.assertIsNone(
            service_audit_block('', datetime.date(2026, 7, 1), datetime.date(2026, 7, 31), 'week'),
        )


class ReportApiPermissionTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        self.client = APIClient()

    def test_preview_requires_admin_or_om(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.get(reverse('report-training-preview'), {'kind': 'week'})
        self.assertEqual(resp.status_code, 403)

    def test_preview_returns_html_for_admin(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('report-training-preview'), {'kind': 'week'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('subject', resp.data)
        self.assertIn('html', resp.data)
        self.assertIn('Báo cáo đào tạo', resp.data['html'])

    def test_send_requires_admin_or_om(self):
        self.client.force_authenticate(self.trainer)
        resp = self.client.post(reverse('report-training-send'), {'kind': 'week'})
        self.assertEqual(resp.status_code, 403)

    def test_send_without_report_to_returns_400(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post(reverse('report-training-send'), {'kind': 'week'})
        self.assertEqual(resp.status_code, 400)
