from decimal import Decimal

from django.conf import settings as django_settings
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import BrandSettings, EmailSettings, GradingConfig, GradingConfigHistory, Tenant, User
from accounts.services import get_email_settings, get_grading_config, update_grading_config


class CreateLoadtestUsersCommandTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_creates_n_accounts_with_prefix_and_role(self):
        call_command(
            'create_loadtest_users', tenant='Demo Tenant', prefix='k6_test_',
            count=3, password='Str0ngPass!', role=User.Role.OM,
        )
        users = User.objects.filter(username__startswith='k6_test_').order_by('username')
        self.assertEqual(list(users.values_list('username', flat=True)), ['k6_test_01', 'k6_test_02', 'k6_test_03'])
        for u in users:
            self.assertEqual(u.tenant_id, self.tenant.id)
            self.assertEqual(u.role, User.Role.OM)
            self.assertTrue(u.check_password('Str0ngPass!'))
            self.assertFalse(u.is_staff)
            self.assertFalse(u.is_superuser)

    def test_rerun_is_idempotent_and_updates_password(self):
        call_command(
            'create_loadtest_users', tenant='Demo Tenant', prefix='k6_test_',
            count=2, password='OldPass!', role=User.Role.OM,
        )
        call_command(
            'create_loadtest_users', tenant='Demo Tenant', prefix='k6_test_',
            count=2, password='NewPass!', role=User.Role.OM,
        )
        users = User.objects.filter(username__startswith='k6_test_')
        self.assertEqual(users.count(), 2)
        for u in users:
            self.assertTrue(u.check_password('NewPass!'))

    def test_does_not_touch_users_with_other_prefix(self):
        other = User.objects.create(username='admin', tenant=self.tenant, role=User.Role.ADMIN)
        call_command(
            'create_loadtest_users', tenant='Demo Tenant', prefix='k6_test_',
            count=1, password='Str0ngPass!', role=User.Role.OM,
        )
        other.refresh_from_db()
        self.assertEqual(other.role, User.Role.ADMIN)
        self.assertFalse(other.check_password('Str0ngPass!'))


class BrandSettingsApiTests(TestCase):
    """UI dot 1 (Prompt_UI_Dot1_Theme.md muc 3c): GET /api/settings/brand/ - ap cho MOI tai
    khoan (ke ca hoc vien), tra ve mac dinh khi tenant chua cau hinh gi."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.other_tenant = Tenant.objects.create(name='Tenant khác')
        self.admin = User.objects.create_user(username='admin1', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()

    def test_returns_model_defaults_when_not_configured(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('brand-settings'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['brand_hex'], '#1e6f5c')
        self.assertEqual(resp.data['theme_mode'], 'light')
        self.assertEqual(resp.data['system_name'], '')
        self.assertFalse(BrandSettings.objects.filter(tenant=self.tenant).exists())  # khong tu tao ban ghi

    def test_returns_configured_brand_for_own_tenant_only(self):
        BrandSettings.objects.create(
            tenant=self.tenant, system_name='Anh Minh Training', brand_hex='#2563eb',
            logo_url='https://pub-x.r2.dev/logo.png',
        )
        BrandSettings.objects.create(tenant=self.other_tenant, system_name='Tenant khác', brand_hex='#dc2626')

        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('brand-settings'))
        self.assertEqual(resp.data['system_name'], 'Anh Minh Training')
        self.assertEqual(resp.data['brand_hex'], '#2563eb')
        self.assertEqual(resp.data['logo_url'], 'https://pub-x.r2.dev/logo.png')

    def test_employee_role_can_read_brand_settings(self):
        from employees.models import Employee

        learner = User.objects.create_user(
            username='nv1', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        Employee.objects.create(tenant=self.tenant, code='NV1', name='NV1', user=learner)
        self.client.force_authenticate(learner)
        resp = self.client.get(reverse('brand-settings'))
        self.assertEqual(resp.status_code, 200)

    def test_requires_authentication(self):
        resp = self.client.get(reverse('brand-settings'))
        self.assertEqual(resp.status_code, 401)

    def test_put_requires_admin(self):
        from employees.models import Employee

        learner = User.objects.create_user(
            username='nv2', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        Employee.objects.create(tenant=self.tenant, code='NV2', name='NV2', user=learner)
        self.client.force_authenticate(learner)
        resp = self.client.put(reverse('brand-settings'), {'system_name': 'Hack'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_put_creates_and_updates_record(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.put(
            reverse('brand-settings'),
            {'system_name': 'Anh Minh Training', 'brand_hex': '#123456', 'favicon_url': 'https://pub-x.r2.dev/f.png'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['system_name'], 'Anh Minh Training')
        self.assertEqual(resp.data['favicon_url'], 'https://pub-x.r2.dev/f.png')
        obj = BrandSettings.objects.get(tenant=self.tenant)
        self.assertEqual(obj.brand_hex, '#123456')


class GradingConfigServiceTests(TestCase):
    """UI dot 3 (Prompt_UI_Dot3_CaiDat_GradingConfig.md muc B): GradingConfig phai externalize
    dung cac hang so hardcode CU MA KHONG DOI KET QUA - mac dinh cua ban ghi tu tao PHAI khop
    dung gia tri DANG CHAY THAT cua settings.COMMISSION_* (khong phai default() khai bao rieng
    o model, vi field default chi la fallback khi KHONG co bien moi truong nao ca)."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')

    def test_defaults_match_current_hardcoded_values_zero_regression(self):
        config = get_grading_config(self.tenant)
        self.assertEqual(config.exam_pass_percent, Decimal(str(django_settings.COMMISSION_EXAM_THRESHOLD)))
        self.assertEqual(config.skill_pass_percent, Decimal(str(django_settings.COMMISSION_SKILL_THRESHOLD)))
        self.assertEqual(config.weight_exam, Decimal('0.4'))
        self.assertEqual(config.weight_practice, Decimal('0.6'))
        self.assertEqual(config.weight_theory, Decimal('50'))
        self.assertEqual(config.weight_practical, Decimal('50'))
        self.assertEqual(config.days_staff, 15)
        self.assertEqual(config.days_supervisor_deputy, 30)
        self.assertEqual(config.days_manager_chef, 60)
        self.assertEqual(config.allowance_per_person, Decimal(str(django_settings.COMMISSION_AMOUNT)))
        self.assertEqual(config.allowance_exam_min, Decimal(str(django_settings.COMMISSION_EXAM_THRESHOLD)))
        self.assertEqual(config.allowance_skill_min, Decimal(str(django_settings.COMMISSION_SKILL_THRESHOLD)))
        self.assertEqual(config.allowance_scope, list(django_settings.COMMISSION_RESTAURANT_ALLOWLIST or []))
        self.assertEqual(config.cert_positions_required, 3)

    def test_get_or_create_is_idempotent(self):
        get_grading_config(self.tenant)
        self.assertEqual(GradingConfig.objects.filter(tenant=self.tenant).count(), 1)
        get_grading_config(self.tenant)
        self.assertEqual(GradingConfig.objects.filter(tenant=self.tenant).count(), 1)

    def test_update_writes_one_history_row_per_changed_field(self):
        admin = User.objects.create_user(username='admin2', password='x', tenant=self.tenant, role='admin')
        config, changed = update_grading_config(
            self.tenant, admin, {'exam_pass_percent': 75, 'days_manager_chef': 45, 'skill_pass_percent': 85},
        )
        self.assertEqual(changed, 2)  # skill_pass_percent khong doi (van 85) -> khong ghi history
        self.assertEqual(config.exam_pass_percent, Decimal('75'))
        self.assertEqual(config.days_manager_chef, 45)
        rows = GradingConfigHistory.objects.filter(tenant=self.tenant).order_by('field')
        self.assertEqual(rows.count(), 2)
        by_field = {r.field: r for r in rows}
        self.assertEqual(Decimal(by_field['exam_pass_percent'].old_value), Decimal('80'))
        self.assertEqual(Decimal(by_field['exam_pass_percent'].new_value), Decimal('75'))
        self.assertEqual(by_field['exam_pass_percent'].changed_by_id, admin.id)

    def test_update_invalidates_cache_next_read_sees_new_value(self):
        get_grading_config(self.tenant)  # tao + cache
        update_grading_config(self.tenant, None, {'exam_pass_percent': 70})
        config = get_grading_config(self.tenant)
        self.assertEqual(config.exam_pass_percent, Decimal('70'))


class GradingConfigApiTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin3', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()

    def test_get_requires_admin(self):
        from employees.models import Employee

        learner = User.objects.create_user(
            username='nv3', password='x', tenant=self.tenant, role=User.Role.EMPLOYEE,
        )
        Employee.objects.create(tenant=self.tenant, code='NV3', name='NV3', user=learner)
        self.client.force_authenticate(learner)
        resp = self.client.get(reverse('grading-config'))
        self.assertEqual(resp.status_code, 403)

    def test_put_updates_and_history_endpoint_returns_rows(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.put(reverse('grading-config'), {'exam_pass_percent': 75}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['exam_pass_percent'], '75.00')

        resp = self.client.get(reverse('grading-config-history'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['field'], 'exam_pass_percent')
        self.assertEqual(Decimal(resp.data[0]['old_value']), Decimal('80'))
        self.assertEqual(Decimal(resp.data[0]['new_value']), Decimal('75'))


class EmailSettingsApiTests(TestCase):
    """UI dot 3 muc A2: KHONG co truong SMTP/mat khau."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.admin = User.objects.create_user(username='admin4', password='x', tenant=self.tenant, role='admin')
        self.client = APIClient()

    def test_no_smtp_or_password_field_in_serializer_output(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.get(reverse('email-settings'))
        self.assertEqual(resp.status_code, 200)
        for forbidden in ('smtp', 'password', 'host', 'port'):
            for key in resp.data:
                self.assertNotIn(forbidden, key.lower())

    def test_put_saves_recipients_and_schedule(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.put(
            reverse('email-settings'),
            {
                'recipients': ['a@x.com', 'b@x.com'], 'cc': ['c@x.com'],
                'weekly_enabled': True, 'weekly_weekday': 0, 'weekly_hour': 8,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['recipients'], ['a@x.com', 'b@x.com'])
        self.assertTrue(resp.data['weekly_enabled'])
        obj = get_email_settings(self.tenant)
        self.assertEqual(obj.cc, ['c@x.com'])
