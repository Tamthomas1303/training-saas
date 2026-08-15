"""
Import khung nang luc tu 2 file CSV xuat tu KhungNangLuc_MucTieu_TheoViTri_v0.5.xlsx (sheet
"Muc tieu theo vi tri" va "Trong so nhom"). Dung khi admin da xuat CSV tu Excel va muon nap
qua dong lenh (thay vi man upload tren web) - cung logic voi 2 endpoint import/targets|weights.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from dashboard.services import ValidationError, import_position_group_weights, import_position_targets


class Command(BaseCommand):
    help = 'Import khung nang luc (muc tieu theo vi tri + trong so nhom) tu 2 file CSV'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--targets', help='Duong dan CSV sheet "Muc tieu theo vi tri"')
        parser.add_argument('--weights', help='Duong dan CSV sheet "Trong so nhom"')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Không tìm thấy tenant '{options['tenant']}'")
        if not options['targets'] and not options['weights']:
            raise CommandError('Cần ít nhất --targets hoặc --weights (đường dẫn file CSV).')

        if options['targets']:
            with open(options['targets'], encoding='utf-8-sig') as f:
                try:
                    result = import_position_targets(tenant, f.read())
                except ValidationError as exc:
                    raise CommandError(str(exc)) from exc
            self.stdout.write(self.style.SUCCESS(
                f"Mục tiêu theo vị trí: ghi {result['targets_written']} dòng, "
                f"{result['positions']} vị trí, {len(result['warnings'])} cảnh báo."
            ))
            for w in result['warnings']:
                self.stdout.write(self.style.WARNING(f'  {w}'))

        if options['weights']:
            with open(options['weights'], encoding='utf-8-sig') as f:
                try:
                    result = import_position_group_weights(tenant, f.read())
                except ValidationError as exc:
                    raise CommandError(str(exc)) from exc
            self.stdout.write(self.style.SUCCESS(
                f"Trọng số nhóm: ghi {result['weights_written']} dòng, {len(result['warnings'])} cảnh báo."
            ))
            for w in result['warnings']:
                self.stdout.write(self.style.WARNING(f'  {w}'))
