from unittest.mock import patch

from django.core import mail
from django.test import TestCase

from accounts.models import Tenant, User

from .models import Notification
from .services import notify_users


class NotifyUsersWebPushTests(TestCase):
    """Nhom 4 (Prompt_Nhom4_PWA_Push.md muc 3): notify_users la diem nghen DUY NHAT tao moi
    thong bao trong he thong - gan web push tai day phai khong lam hong luong in-app/email da co
    du push loi/thieu VAPID, va phai goi push cho DUNG tung nguoi nhan."""

    def setUp(self):
        mail.outbox = []
        self.tenant = Tenant.objects.create(name='Demo Tenant')
        self.u1 = User.objects.create_user(
            username='u1', password='x', email='u1@example.com', tenant=self.tenant, role='bql',
        )
        self.u2 = User.objects.create_user(
            username='u2', password='x', email='u2@example.com', tenant=self.tenant, role='bql',
        )

    @patch('accounts.services.send_web_push')
    def test_calls_send_web_push_for_each_recipient(self, mock_push):
        notify_users([self.u1, self.u2], title='Tiêu đề', body='Nội dung', link='/x', category='cat')
        self.assertEqual(mock_push.call_count, 2)
        called_users = {c.args[0] for c in mock_push.call_args_list}
        self.assertEqual(called_users, {self.u1, self.u2})

    @patch('accounts.services.send_web_push')
    def test_in_app_and_email_unaffected_when_push_raises(self, mock_push):
        mock_push.side_effect = RuntimeError('push service unreachable')
        count = notify_users([self.u1], title='Tiêu đề', body='Nội dung', link='/x', category='cat')
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(user=self.u1, category='cat').exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_notify_users_still_works_when_accounts_services_missing_attribute(self):
        """Import mem (Nhom 4 muc 3 'import mem de khong loi neu thieu VAPID') - gia lap truong
        hop send_web_push khong ton tai (vd loi cau hinh) van khong duoc lam hong notify_users."""
        with patch('accounts.services.send_web_push', side_effect=AttributeError('boom')):
            count = notify_users([self.u1], title='T', body='B', link='', category='cat')
        self.assertEqual(count, 1)
        self.assertTrue(Notification.objects.filter(user=self.u1, category='cat').exists())
