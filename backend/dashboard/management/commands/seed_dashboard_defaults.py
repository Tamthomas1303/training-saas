from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from dashboard.services import seed_competency_framework, seed_dashboard_indicators


class Command(BaseCommand):
    help = 'Seed 6 nhom + 24 nang luc khoi diem va danh sach chi so Dashboard da chon (idempotent)'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{options['tenant']}'")

        framework = seed_competency_framework(tenant)
        indicators = seed_dashboard_indicators(tenant)
        self.stdout.write(self.style.SUCCESS(
            f"Đã tạo {framework['groups_created']} nhóm, {framework['competencies_created']} năng lực, "
            f"{indicators['indicators_created']} chỉ số dashboard mới."
        ))
