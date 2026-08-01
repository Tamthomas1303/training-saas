import datetime
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Tenant, User
from cls_sync.models import ExamResult
from employees.models import Employee
from restaurants.models import Restaurant

from .chart import render_service_score_chart
from .gpt import _strip_code_fences, build_block_analysis
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

    @patch('reports.metrics_csv.requests.get')
    def test_finds_header_row_past_leading_blank_and_title_rows(self, mock_get):
        """Sheet nguon co dong trong + dong tieu de truoc dong header that - phai tim dung
        dong header (chua Training_Date + Employee_ID) thay vi coi dong dau la header.
        Bao cao Tuan 27/07-02/08/2026 phai thay 2 lop (ngay 30, 31)."""
        csv_text = (
            '\n'
            'BAO CAO TO CHUC DAO TAO - THANG 7/2026\n'
            '\n'
            'Training_Date,Employee_ID,Employee_Name,Cousera_Code,Cousera_Name,Class_Code,'
            'Learner_Group,Assignment_Status,Participation_Status,Training_Month\n'
            '30/07/2026,NV1,A,C1,Lop Pha che,C1,G1,Đã gán,Đã tham gia,07/2026\n'
            '31/07/2026,NV2,B,C2,Lop An toan thuc pham,C2,G1,Đã gán,Đã tham gia,07/2026\n'
        )
        mock_get.return_value = FakeResponse(csv_text)
        result = training_org_block('http://fake-url', datetime.date(2026, 7, 27), datetime.date(2026, 8, 2))
        self.assertEqual(result['total_classes'], 2)
        self.assertEqual(result['total_assigned'], 2)
        self.assertEqual(result['total_attended'], 2)
        self.assertEqual({c['name'] for c in result['classes']}, {'Lop Pha che', 'Lop An toan thuc pham'})


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

    def test_send_always_returns_guidance_instead_of_sending(self):
        """Gui truc tiep tu web da bi vo hieu hoa (Render chan SMTP) - endpoint CHI tra ve
        huong dan, khong bao gio thu goi SMTP, du REPORT_TO co cau hinh hay khong."""
        self.client.force_authenticate(self.admin)
        with override_settings(REPORT_TO=['a@example.com']):
            with patch('reports.services.send_report_email') as mock_send:
                resp = self.client.post(reverse('report-training-send'), {'kind': 'week'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('SMTP', resp.data['detail'])
        mock_send.assert_not_called()  # dam bao view khong con goi SMTP truc tiep nua


class SendTrainingReportCommandTests(TestCase):
    """management command chay tu GitHub Actions (khong bi Render chan SMTP) - dung lai
    send_report_email() da co san, chi la lop CLI."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_raises_when_tenant_missing(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('send_training_report', tenant='Khong Ton Tai')

    def test_raises_when_report_to_not_configured(self):
        from django.core.management.base import CommandError

        with override_settings(REPORT_TO=[]):
            with self.assertRaises(CommandError):
                call_command('send_training_report', kind='week')

    def test_raises_on_invalid_date(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('send_training_report', date='not-a-date')

    @override_settings(REPORT_TO=['ops@example.com'])
    def test_sends_email_for_given_kind_and_date(self):
        from io import StringIO

        # stdout=StringIO tranh loi encode cp1252 cua console Windows voi ky tu tieng Viet
        # (khong lien quan production - GitHub Actions runner dung UTF-8).
        call_command('send_training_report', kind='week', date='2026-07-30', stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('ops@example.com', mail.outbox[0].to)
        self.assertIn('Tuần', mail.outbox[0].subject)


class ServiceAuditByColumnNameTests(TestCase):
    """MUC 1: sheet that co dong header ten cot (khong phai vi tri co dinh) - phai anh xa
    theo TEN + dung Result_Text='KHÔNG' de xac dinh "van de" (khong con result_score==0)."""

    HEADER = [
        'Assessment_ID', 'Timestamp', 'Assessor', 'Assess_Date', 'Restaurant_ID',
        'Restaurant_Name', 'Brand_Name', 'Ques_Num', 'Score_Criteria', 'Criteria',
        'Category', 'Main_Category', 'Result_Text', 'Result_Score', 'Department_Name', 'Note',
    ]

    def _row(self, date_, restaurant, score_criteria, criteria, result_text, result_score, dept):
        cells = ['x'] * len(self.HEADER)
        cells[3] = date_
        cells[5] = restaurant
        cells[8] = str(score_criteria)
        cells[9] = criteria
        cells[12] = result_text
        cells[13] = str(result_score)
        cells[14] = dept
        return cells

    @patch('reports.metrics_csv.requests.get')
    def test_maps_by_column_name_and_uses_result_text(self, mock_get):
        csv_text = '\n'.join([
            ','.join(self.HEADER),
            ','.join(self._row('05/07/2026', 'NH A', 10, 'Ve sinh', 'ĐẠT', 10, 'Phòng Đào tạo')),
            # Result_Text=KHONG nhung diem >0 - van phai tinh la "van de" (uu tien Result_Text
            # hon result_score==0, dung yeu cau moi thay vi logic result_score==0 cu).
            ','.join(self._row('06/07/2026', 'NH A', 10, 'Thai do', 'KHÔNG', 3, 'Phòng Đào tạo')),
            ','.join(self._row('07/07/2026', 'NH A', 10, 'Ve sinh', 'ĐẠT', 10, 'Phòng QA-QC')),
        ])
        mock_get.return_value = FakeResponse(csv_text)
        result = service_audit_block('http://fake-url', datetime.date(2026, 7, 1), datetime.date(2026, 7, 31), 'week')
        self.assertEqual(result['restaurants'], [{'restaurant': 'NH A', 'score': 65.0}])
        self.assertEqual(result['top_problems'], [{'criteria': 'Thai do', 'count': 1}])

    @patch('reports.metrics_csv.requests.get')
    def test_month_top5_no_longer_requires_count_gte_2(self, mock_get):
        rows = [','.join(self.HEADER)]
        for i in range(3):
            rows.append(','.join(self._row(
                f'0{i+1}/07/2026', 'NH A', 1, f'Tieu chi {i}', 'KHÔNG', 0, 'Phòng Đào tạo',
            )))
        mock_get.return_value = FakeResponse('\n'.join(rows))
        result = service_audit_block('http://fake-url', datetime.date(2026, 7, 1), datetime.date(2026, 7, 31), 'month')
        # Truoc day: loc count>=2 -> 0 ket qua. Gio: khong loc nguong, moi tieu chi chi xuat
        # hien 1 lan van duoc liet ke (toi da 5).
        self.assertEqual(len(result['top_problems']), 3)


class SLevelAndCompanyRateTests(TestCase):
    """MUC 4 + MUC 5: loai khoi OFFICE khoi cac chi so cap S/slow_restaurants, chuan hoa cong
    thuc cap S (loai danh gia roi thang sau) + them chi so company_rate (toan cong ty)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def _emp(self, code, level_group, operation_unit, start_date, final_result='',
             status=Employee.EmployeeStatus.PROBATION):
        return Employee.objects.create(
            tenant=self.tenant, code=code, name=f'NV {code}', level_group=level_group,
            operation_unit=operation_unit, start_date=start_date, final_result=final_result,
            employee_status=status,
        )

    def test_s_level_excludes_office_and_eval_next(self):
        self._emp('S1', 'S', Employee.OperationUnit.RESTAURANT, datetime.date(2026, 7, 5), final_result='Pass thử việc')
        self._emp('S2', 'S', Employee.OperationUnit.OFFICE, datetime.date(2026, 7, 5), final_result='Pass thử việc')
        self._emp('S3', 'S', Employee.OperationUnit.RESTAURANT, datetime.date(2026, 7, 20))  # han 8/4 > 7/31
        self._emp('P1', 'P', Employee.OperationUnit.RESTAURANT, datetime.date(2026, 7, 5), final_result='Pass thử việc')

        result = new_hires_block(self.tenant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 31), datetime.date(2026, 7, 31))
        self.assertEqual(result['s_level_total'], 1)
        self.assertEqual(result['s_level_passed'], 1)
        self.assertEqual(result['s_level_rate'], 100.0)

    def test_slow_restaurants_excludes_office(self):
        restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo')
        for i in range(2):
            Employee.objects.create(
                tenant=self.tenant, code=f'OF{i}', name=f'NV OF{i}', restaurant=restaurant,
                operation_unit=Employee.OperationUnit.OFFICE, employee_status=Employee.EmployeeStatus.PROBATION,
            )
        result = new_hires_block(self.tenant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 31), datetime.date(2026, 7, 31))
        self.assertEqual(result['slow_restaurants'], [])  # 2 NV nhung deu OFFICE -> loai het

    def test_company_rate_includes_all_levels_by_eval_date(self):
        self._emp('S1', 'S', Employee.OperationUnit.RESTAURANT, datetime.date(2026, 7, 5), final_result='Pass thử việc')
        self._emp('O1', 'O', Employee.OperationUnit.OFFICE, datetime.date(2026, 6, 1))  # eval_date = 6/1+60 = 7/31
        self._emp('S2', 'S', Employee.OperationUnit.RESTAURANT, datetime.date(2026, 7, 25))  # eval_date 8/9 - ngoai thang

        result = new_hires_block(self.tenant, datetime.date(2026, 7, 1), datetime.date(2026, 7, 31), datetime.date(2026, 7, 31))
        self.assertEqual(result['company_total'], 2)
        self.assertEqual(result['company_passed'], 1)
        self.assertEqual(result['company_rate'], 50.0)


class BuildBlockAnalysisTests(TestCase):
    """MUC 3: nhan dinh GPT ngan cho khoi 1/2/3."""

    def test_returns_none_without_api_key(self):
        with override_settings(OPENAI_API_KEY=''):
            result = build_block_analysis('Đào tạo nhân sự mới', 'Tuần 1', 'so lieu hien tai', 'so lieu ky truoc')
        self.assertIsNone(result)

    @override_settings(OPENAI_API_KEY='test-key')
    @patch('reports.gpt.requests.post')
    def test_calls_openai_with_topic_and_summaries(self, mock_post):
        mock_post.return_value.raise_for_status = lambda: None
        mock_post.return_value.json = lambda: {'choices': [{'message': {'content': '<ul><li>ok</li></ul>'}}]}
        result = build_block_analysis('Kiểm tra kiến thức', 'Tuần 1', 'so lieu hien tai X', 'so lieu ky truoc Y')
        self.assertEqual(result, '<ul><li>ok</li></ul>')
        sent_prompt = mock_post.call_args.kwargs['json']['messages'][1]['content']
        self.assertIn('Kiểm tra kiến thức', sent_prompt)
        self.assertIn('so lieu hien tai X', sent_prompt)
        self.assertIn('so lieu ky truoc Y', sent_prompt)

    @override_settings(OPENAI_API_KEY='test-key')
    @patch('reports.gpt.requests.post')
    def test_strips_code_fence_wrapping_gpt_output(self, mock_post):
        """GPT doi khi tra ve boc trong rao ```html ... ``` du prompt yeu cau CHI tra HTML -
        phai cat bo, khong de hien nguyen rao tren bao cao."""
        mock_post.return_value.raise_for_status = lambda: None
        mock_post.return_value.json = lambda: {
            'choices': [{'message': {'content': '```html\n<ul><li>ok</li></ul>\n```'}}],
        }
        result = build_block_analysis('Tổ chức đào tạo', 'Tuần 1', 'so lieu hien tai', 'so lieu ky truoc')
        self.assertEqual(result, '<ul><li>ok</li></ul>')


class StripCodeFencesTests(TestCase):
    def test_strips_html_fence(self):
        self.assertEqual(_strip_code_fences('```html\n<ul><li>a</li></ul>\n```'), '<ul><li>a</li></ul>')

    def test_strips_bare_fence(self):
        self.assertEqual(_strip_code_fences('```\n<b>x</b>\n```'), '<b>x</b>')

    def test_no_fence_unchanged(self):
        self.assertEqual(_strip_code_fences('<ul><li>a</li></ul>'), '<ul><li>a</li></ul>')

    def test_none_and_empty(self):
        self.assertIsNone(_strip_code_fences(None))
        self.assertEqual(_strip_code_fences(''), '')


class ServiceChartLayoutTests(TestCase):
    """MUC 6: bieu do rong/cao hon de nhan ten nha hang khong bi cat/chong nhau."""

    def test_wider_taller_layout(self):
        from io import BytesIO

        from PIL import Image

        png = render_service_score_chart([
            {'restaurant': 'NH A', 'score': 80}, {'restaurant': 'NH B', 'score': 50},
        ])
        img = Image.open(BytesIO(png))
        self.assertEqual(img.height, 420)
        self.assertGreaterEqual(img.width, 560)


class TrainingOrgEmptyPeriodLogTests(TestCase):
    """MUC 7.2: phan biet "sai cau hinh" (0 dong doc duoc) voi "khong co du lieu trong ky"
    (doc duoc N dong nhung khong dong nao roi vao ky) bang 1 dong log - KHONG doi logic doc."""

    @patch('reports.metrics_csv.requests.get')
    def test_logs_info_when_rows_exist_but_none_in_period(self, mock_get):
        csv_text = (
            'Training_Date,Employee_ID,Employee_Name,Cousera_Code,Cousera_Name,Class_Code,'
            'Learner_Group,Assignment_Status,Participation_Status,Training_Month\n'
            '05/11/2025,NV1,A,C1,Lop Cu,C1,G1,Đã gán,Đã tham gia,11/2025\n'
        )
        mock_get.return_value = FakeResponse(csv_text)
        with self.assertLogs('reports.metrics_csv', level='INFO') as captured:
            result = training_org_block('http://fake-url', datetime.date(2026, 7, 27), datetime.date(2026, 8, 2))
        self.assertEqual(result['total_classes'], 0)
        self.assertTrue(any('0 dong trong' in msg for msg in captured.output))
