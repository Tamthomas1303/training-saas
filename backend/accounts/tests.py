from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import BrandSettings, Tenant, User


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
