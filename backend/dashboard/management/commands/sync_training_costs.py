"""
sync_training_costs — nap chi phi dao tao tu nguon CSV (Google Sheet Publish to web > CSV),
theo dung cau truc File_HachToan_ChiPhiDaoTao_MAU.xlsx (Prompt_Dashboard_B_ManTongHop.md, muc 4).

Thu tu lay link: --csv-url > TrainingCostSource (cau hinh tren giao dien).
Cung co che voi employees/sync_recruitment.py.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from dashboard.models import TrainingCostSource
from dashboard.services import ValidationError, import_training_costs


class Command(BaseCommand):
    help = 'Keo chi phi dao tao tu nguon CSV vao bang TrainingCost'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--csv-url', default=None, help='Ghi de link CSV (uu tien cao nhat)')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{options['tenant']}'")

        csv_url = options['csv_url']
        if not csv_url:
            src = TrainingCostSource.objects.filter(tenant=tenant).first()
            csv_url = src.csv_url if src else ''
        if not csv_url:
            raise CommandError(
                'Chưa cấu hình link CSV. Đặt trên giao diện hoặc truyền --csv-url.'
            )

        from config.csv_source import load_csv_rows

        try:
            rows = load_csv_rows(csv_url)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f'Không đọc được nguồn dữ liệu: {exc}') from exc

        try:
            result = import_training_costs(tenant, rows)
        except ValidationError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"Chi phí đào tạo: ghi {result['written']} dòng, {len(result['warnings'])} cảnh báo."
        ))
        for w in result['warnings']:
            self.stdout.write(self.style.WARNING(f'  {w}'))
