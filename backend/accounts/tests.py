from django.core.management import call_command
from django.test import TestCase

from accounts.models import Tenant, User


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
