import datetime
from unittest.mock import patch

from django.test import TestCase

from accounts.models import Tenant, User, UserRestaurantAssignment
from employees.models import Employee
from evaluation.models import Evaluation
from restaurants.models import Restaurant

from .models import Commission, ExportedReport
from .services import (
    _bql_cohort_stats,
    allowance_report_data,
    generate_allowance_pdf,
    generate_kpi_report_pdf,
    get_exported_report_url,
    kpi_bql_report_data,
    recompute_commission,
)


class RecomputeCommissionTrainerRoleTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_bql_trainer_sets_na_and_hides_existing_eligible(self):
        bql = User.objects.create_user(username='bql1', password='x', tenant=self.tenant, role='bql')
        employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV Demo', trainer=bql)
        Commission.objects.create(
            tenant=self.tenant, employee=employee, trainer=bql, status=Commission.Status.ELIGIBLE,
        )

        result = recompute_commission(employee)

        self.assertEqual(result.status, Commission.Status.NA)

    def test_no_trainer_sets_na(self):
        employee = Employee.objects.create(tenant=self.tenant, code='NV2', name='NV Demo 2')

        result = recompute_commission(employee)

        self.assertIsNone(result)

    def test_trainer_role_proceeds_normally(self):
        trainer = User.objects.create_user(username='trainer1', password='x', tenant=self.tenant, role='trainer')
        employee = Employee.objects.create(tenant=self.tenant, code='NV3', name='NV Demo 3', trainer=trainer)

        result = recompute_commission(employee)

        self.assertIsNotNone(result)
        self.assertEqual(result.trainer_id, trainer.id)
        self.assertNotEqual(result.status, Commission.Status.NA)

    def test_paid_commission_stays_paid_even_if_trainer_is_bql(self):
        bql = User.objects.create_user(username='bql2', password='x', tenant=self.tenant, role='bql')
        employee = Employee.objects.create(tenant=self.tenant, code='NV4', name='NV Demo 4', trainer=bql)
        Commission.objects.create(
            tenant=self.tenant, employee=employee, trainer=bql, status=Commission.Status.PAID,
        )

        result = recompute_commission(employee)

        self.assertEqual(result.status, Commission.Status.PAID)


class BqlCohortStatsTests(TestCase):
    """Cong thuc bao cao KPI BQL (Phan B - Prompt v2.1_Port_ThayDoi 05-06/08/2026)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        # Ky bao cao: thang 8/2026. Tier mac dinh (khong phai giam sat/bep pho/quan ly/bep
        # truong) = 15 ngay -> vao 2026-07-20 thi han danh gia 2026-08-04 (trong ky).
        self.month, self.year = 8, 2026

    def _employee(self, code, **kwargs):
        defaults = dict(tenant=self.tenant, name=code, restaurant=self.restaurant, position='Phục vụ')
        defaults.update(kwargs)
        return Employee.objects.create(code=code, **defaults)

    def test_on_track_uses_pass_date_not_checklist_completion(self):
        e = self._employee(
            'NV1', start_date=datetime.date(2026, 7, 20),
            pass_date=datetime.date(2026, 8, 1),  # trong han 15 ngay
        )

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        row = by_restaurant[self.restaurant.id]
        self.assertEqual(row['on_den'], 1)
        self.assertEqual(row['on_num'], 1)

    def test_no_pass_date_not_on_track(self):
        e = self._employee('NV1', start_date=datetime.date(2026, 7, 20), pass_date=None)

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        row = by_restaurant[self.restaurant.id]
        self.assertEqual(row['on_den'], 1)
        self.assertEqual(row['on_num'], 0)

    def test_pass_date_beyond_tier_not_on_track(self):
        e = self._employee(
            'NV1', start_date=datetime.date(2026, 7, 20),
            pass_date=datetime.date(2026, 8, 20),  # qua han 15 ngay
        )

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        row = by_restaurant[self.restaurant.id]
        self.assertEqual(row['on_num'], 0)

    def test_resigned_employee_excluded_from_cohort_but_counted_in_note(self):
        e = self._employee(
            'NV1', start_date=datetime.date(2026, 7, 20),
            employee_status=Employee.EmployeeStatus.RESIGNED,
        )

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        row = by_restaurant[self.restaurant.id]
        self.assertEqual(row['on_den'], 0)
        self.assertEqual(row['excl_resigned'], 1)

    def test_parttime_p_excluded_silently(self):
        e = self._employee('NV1', start_date=datetime.date(2026, 7, 20), job_level='P1')

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        self.assertNotIn(self.restaurant.id, by_restaurant)

    def test_hired_this_period_deadline_next_period_counted_as_excl_next_period(self):
        # Quan ly (tier 60 ngay): vao 2026-08-01 -> han 2026-09-30, roi sang ky sau.
        e = self._employee(
            'NV1', position='Quản lý nhà hàng', start_date=datetime.date(2026, 8, 1),
        )

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        row = by_restaurant[self.restaurant.id]
        self.assertEqual(row['on_den'], 0)
        self.assertEqual(row['excl_next_period'], 1)

    def test_restaurant_listed_even_at_zero_zero_with_exclusion_note(self):
        e = self._employee(
            'NV1', start_date=datetime.date(2026, 7, 20),
            employee_status=Employee.EmployeeStatus.RESIGNED,
        )

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        self.assertIn(self.restaurant.id, by_restaurant)
        row = by_restaurant[self.restaurant.id]
        self.assertEqual(row['on_den'], 0)
        self.assertEqual(row['excl_resigned'], 1)

    def test_skill_uses_earliest_evaluation_not_latest(self):
        e = self._employee('NV1', start_date=datetime.date(2026, 7, 20))
        evaluator = User.objects.create_user(username='ev1', password='x', tenant=self.tenant, role='bql')
        # Lan dau THANG 5 (som nhat) = Khong dat; lan 2 THANG 8 (trong ky) = Dat - phai tinh
        # theo lan DAU (Khong dat), khong phai lan gan nhat.
        Evaluation.objects.create(
            tenant=self.tenant, employee=e, evaluator=evaluator, eval_type='Skill_BQL',
            status='done', date=datetime.date(2026, 5, 1), result=Evaluation.Result.FAIL,
        )
        Evaluation.objects.create(
            tenant=self.tenant, employee=e, evaluator=evaluator, eval_type='Skill_BQL',
            status='done', date=datetime.date(2026, 8, 1), result=Evaluation.Result.PASS,
        )

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        row = by_restaurant[self.restaurant.id]
        self.assertEqual(row['skill_total'], 1)
        self.assertEqual(row['skill_pass'], 0)

    def test_no_start_date_skipped(self):
        e = self._employee('NV1', start_date=None)

        by_restaurant = _bql_cohort_stats([e], self.month, self.year)

        self.assertEqual(by_restaurant, {})


class KpiBqlReportDataTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')

    def test_returns_rows_totals_and_am_kcs(self):
        Employee.objects.create(
            tenant=self.tenant, code='NV1', name='NV1', restaurant=self.restaurant, position='Phục vụ',
            start_date=datetime.date(2026, 7, 20), pass_date=datetime.date(2026, 8, 1),
        )

        data = kpi_bql_report_data(self.admin, 8, 2026)

        self.assertEqual(len(data['rows']), 1)
        self.assertEqual(data['totals']['on_num'], 1)
        self.assertEqual(data['totals']['on_den'], 1)
        self.assertEqual(data['totals']['on_rate'], 100)
        self.assertEqual(len(data['am_kcs']), 2)
        self.assertEqual(data['am_kcs'][0]['label'], 'AM (toàn hệ thống)')

    def test_am_kcs_averages_rates_not_totals(self):
        r2 = Restaurant.objects.create(tenant=self.tenant, code='NH2', name='NH2', brand='Kampong')
        # NH1: 1/1 = 100% ; NH2: 0/1 = 0% -> trung binh cong = 50% (khac tong gop 1/2=50% trung
        # hop o day, nen dung so lieu lech han de phan biet: NH1 co 3 nguoi dat 100%.
        for i in range(3):
            Employee.objects.create(
                tenant=self.tenant, code=f'A{i}', name=f'A{i}', restaurant=self.restaurant, position='Phục vụ',
                start_date=datetime.date(2026, 7, 20), pass_date=datetime.date(2026, 8, 1),
            )
        Employee.objects.create(
            tenant=self.tenant, code='B1', name='B1', restaurant=r2, position='Phục vụ',
            start_date=datetime.date(2026, 7, 20), pass_date=None,
        )

        data = kpi_bql_report_data(self.admin, 8, 2026)

        # Tong gop: 3/4 = 75%. Trung binh cong 2 nha hang (100%, 0%) = 50%.
        self.assertEqual(data['totals']['on_rate'], 75)
        am_row = next(r for r in data['am_kcs'] if r['label'].startswith('AM'))
        self.assertEqual(am_row['on_rate'], 50)

    def test_kcs_scope_limited_to_kitchen_positions_in_assigned_restaurants(self):
        kitchen_emp = Employee.objects.create(
            tenant=self.tenant, code='K1', name='K1', restaurant=self.restaurant, position='Bếp thớt',
            start_date=datetime.date(2026, 7, 20), pass_date=datetime.date(2026, 8, 1),
        )
        Employee.objects.create(
            tenant=self.tenant, code='F1', name='F1', restaurant=self.restaurant, position='Phục vụ',
            start_date=datetime.date(2026, 7, 20), pass_date=None,
        )
        kcs_user = User.objects.create_user(username='kcs1', password='x', tenant=self.tenant, role='kcs')
        UserRestaurantAssignment.objects.create(user=kcs_user, restaurant=self.restaurant)

        data = kpi_bql_report_data(self.admin, 8, 2026)

        kcs_row = next(r for r in data['am_kcs'] if r['label'].startswith('KCS'))
        # Chi tinh Bep thot (Dat) - bo qua Phuc vu -> 100%, khong phai trung binh voi FOH.
        self.assertEqual(kcs_row['on_rate'], 100)
        self.assertEqual(kcs_row['restaurant_count'], 1)


class AllowanceReportDataTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.restaurant = Restaurant.objects.create(tenant=self.tenant, code='NH1', name='NH Demo', brand='Kampong')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')

    def test_rows_include_trainer_code_and_restaurant(self):
        trainer = User.objects.create_user(
            username='trainer_am001', password='x', tenant=self.tenant, role='trainer', restaurant=self.restaurant,
        )
        employee = Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', trainer=trainer)
        Commission.objects.create(
            tenant=self.tenant, employee=employee, trainer=trainer, status=Commission.Status.ELIGIBLE, amount=300000,
        )

        data = allowance_report_data(self.admin, 8, 2026)

        self.assertEqual(len(data['rows']), 1)
        row = data['rows'][0]
        self.assertEqual(row['trainer_code'], 'trainer_am001')
        self.assertEqual(row['trainer_restaurant'], 'NH Demo')


class ExportedReportPersistenceTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')

    @patch('kpi.services.upload_pdf_bytes')
    def test_generate_kpi_report_pdf_saves_and_returns_exported_report(self, mock_upload):
        mock_upload.return_value = 'https://pub-x.r2.dev/baocao/1/kpi/x.pdf'

        pdf_url = generate_kpi_report_pdf(self.admin, 8, 2026)

        self.assertEqual(pdf_url, 'https://pub-x.r2.dev/baocao/1/kpi/x.pdf')
        self.assertEqual(
            get_exported_report_url(self.tenant, ExportedReport.Kind.KPI_BQL, 8, 2026), pdf_url,
        )

    @patch('checklist.storage.delete_by_url')
    @patch('kpi.services.upload_pdf_bytes')
    def test_re_export_deletes_old_file_and_replaces_url(self, mock_upload, mock_delete):
        mock_upload.return_value = 'https://pub-x.r2.dev/first.pdf'
        generate_kpi_report_pdf(self.admin, 8, 2026)

        mock_upload.return_value = 'https://pub-x.r2.dev/second.pdf'
        pdf_url = generate_kpi_report_pdf(self.admin, 8, 2026)

        self.assertEqual(pdf_url, 'https://pub-x.r2.dev/second.pdf')
        self.assertEqual(
            get_exported_report_url(self.tenant, ExportedReport.Kind.KPI_BQL, 8, 2026), pdf_url,
        )
        self.assertEqual(ExportedReport.objects.count(), 1)

    def test_no_export_yet_returns_empty_string(self):
        self.assertEqual(get_exported_report_url(self.tenant, ExportedReport.Kind.ALLOWANCE, 8, 2026), '')

    @patch('kpi.services.upload_pdf_bytes')
    def test_allowance_export_saved_separately_from_kpi_report(self, mock_upload):
        mock_upload.return_value = 'https://pub-x.r2.dev/allowance.pdf'

        generate_allowance_pdf(self.admin, 8, 2026)

        self.assertEqual(
            get_exported_report_url(self.tenant, ExportedReport.Kind.ALLOWANCE, 8, 2026),
            'https://pub-x.r2.dev/allowance.pdf',
        )
        self.assertEqual(get_exported_report_url(self.tenant, ExportedReport.Kind.KPI_BQL, 8, 2026), '')
