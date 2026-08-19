"""create_loadtest_users — tao/dam bao co san vai tai khoan rieng cho k6 (loadtest/k6_v21_loadtest.js).

Idempotent: chay lai voi cung --prefix/--count se KHONG tao trung, chi cap nhat mat khau/role/tenant
neu da ton tai (vd doi mat khau truoc moi dot load test). Dat rieng prefix (mac dinh 'k6_test_') de
khong dung cham voi tai khoan nguoi dung that.

Vai tro mac dinh 'om': vua xem duoc Dashboard tong hop (admin/om/bod), vua xem duoc Bao cao KPI BQL
(chi admin/om) - de k6 goi ca 2 nhom endpoint ma khong bi 403 lam sai lech ty le loi.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant, User


class Command(BaseCommand):
    help = "Tao/dam bao co san N tai khoan rieng cho k6 load test (khong dung chung voi user that)."

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--prefix', default='k6_test_')
        parser.add_argument('--count', type=int, default=5)
        parser.add_argument('--password', required=True, help='Mat khau chung cho cac tai khoan test (truyen tay, khong dat mac dinh).')
        parser.add_argument('--role', default=User.Role.OM, choices=[User.Role.ADMIN, User.Role.OM, User.Role.BOD])

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{options['tenant']}'.")

        prefix, count, role = options['prefix'], options['count'], options['role']
        created_count, updated_count = 0, 0

        for i in range(1, count + 1):
            username = f"{prefix}{i:02d}"
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'tenant': tenant, 'role': role,
                    'full_name': f'K6 Load Test {i:02d}',
                },
            )
            user.set_password(options['password'])
            user.tenant = tenant
            user.role = role
            user.full_name = user.full_name or f'K6 Load Test {i:02d}'
            user.is_staff = False
            user.is_superuser = False
            user.save()
            if created:
                created_count += 1
            else:
                updated_count += 1
            self.stdout.write(f"  {'Tạo mới' if created else 'Đã có, cập nhật'}: {username} (role={role}, tenant={tenant.name})")

        self.stdout.write(self.style.SUCCESS(
            f"\nXong: {created_count} tài khoản mới, {updated_count} tài khoản đã cập nhật. "
            f"Dùng -e TEST_USER_PREFIX=\"{prefix}\" -e TEST_USER_COUNT={count} khi chạy k6."
        ))
