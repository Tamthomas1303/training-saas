"""
refresh_competency_snapshots — tinh NEN CompetencySnapshot/CompetencyScoreSnapshot cho tung
nhan su (Prompt_Fix_OOM_DashboardTongHop.md). Man tong hop CEO/GDDT truoc day goi
compute_competency_scores() cho TOAN BO nhan su trong 1 request HTTP -> OOM tren Render free
512MB voi tenant lon (~1.240 nhan su). Lenh nay dung LAI DUNG engine do nhung chay NGOAI request
(chay tay hoac qua lich dinh ky - xem .github/workflows/refresh_competency_snapshots.yml), nen
du co nang cung khong lam sap worker phuc vu web.

Chay tay: python manage.py refresh_competency_snapshots --tenant "Demo Tenant"
Nen chay dinh ky (vai gio/lan hoac qua dem) qua GitHub Actions (cung co che sync_cls.yml) hoac
Render Cron Job - xem README/README_DEPLOY de cau hinh lich.
"""
import time

from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from dashboard.services import refresh_competency_snapshots


class Command(BaseCommand):
    help = 'Tinh nen diem nang luc (CompetencySnapshot) cho man tong hop CEO/GDDT - chay nen/cron, khong goi tu web request'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default=None, help='Ten tenant (mac dinh: tat ca tenant)')

    def handle(self, *args, **options):
        tenants = (
            [self._get_tenant(options['tenant'])] if options['tenant'] else list(Tenant.objects.all())
        )
        for tenant in tenants:
            started = time.monotonic()
            result = refresh_competency_snapshots(tenant)
            elapsed = round(time.monotonic() - started, 1)
            self.stdout.write(self.style.SUCCESS(
                f"[{tenant.name}] Đã tính lại snapshot năng lực cho {result['updated']} nhân sự ({elapsed}s)."
            ))

    def _get_tenant(self, name):
        tenant = Tenant.objects.filter(name=name).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{name}'")
        return tenant
