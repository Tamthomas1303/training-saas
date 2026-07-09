from django.core.management.base import BaseCommand

from accounts.models import Tenant, User


class Command(BaseCommand):
    help = "Tạo Tenant đầu tiên và tài khoản admin để đăng nhập thử"

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--username', default='admin')
        parser.add_argument('--password', default='admin12345')

    def handle(self, *args, **options):
        tenant, _ = Tenant.objects.get_or_create(name=options['tenant'])

        user, created = User.objects.get_or_create(
            username=options['username'],
            defaults={
                'tenant': tenant,
                'full_name': 'Administrator',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        user.set_password(options['password'])
        user.tenant = tenant
        user.is_staff = True
        user.is_superuser = True
        user.role = User.Role.ADMIN
        user.save()

        action = 'Tạo mới' if created else 'Cập nhật'
        self.stdout.write(self.style.SUCCESS(
            f"{action} user '{user.username}' (tenant='{tenant.name}') với mật khẩu '{options['password']}'"
        ))
