"""
import_checklist — nap checklist noi dung dao tao that tu Google Sheet (Publish to web > CSV)
vao bang Checklist. Chay lai khong nhan doi (update_or_create theo tenant + brand + position + task_name).

Cot CSV (dung ten, khong phan biet hoa/thuong):
  brand, position, day, category, task_name, description, doc_url, level_group, order

Nguon: dat CHECKLIST_SOURCE_CSV_URL (.env / secret) hoac truyen --csv-url.
Them --clear-sample de xoa cac dong checklist mau (brand 'Brand A'/'Brand B') do seed_sample_data tao.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import requests

from accounts.models import Tenant
from checklist.models import Checklist
from config.csv_source import load_csv_rows, pick

SAMPLE_BRANDS = ('Brand A', 'Brand B')


def _to_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


class Command(BaseCommand):
    help = 'Nap checklist noi dung dao tao that tu CSV vao bang Checklist'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--csv-url', default=None, help='Ghi de CHECKLIST_SOURCE_CSV_URL')
        parser.add_argument('--clear-sample', action='store_true', help="Xoa checklist mau (brand 'Brand A'/'Brand B')")

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        if options['clear_sample']:
            deleted, _ = Checklist.objects.filter(tenant=tenant, brand__in=SAMPLE_BRANDS).delete()
            self.stdout.write(self.style.WARNING(f'Da xoa {deleted} ban ghi checklist mau (Brand A/B)'))

        csv_url = options['csv_url'] or getattr(settings, 'CHECKLIST_SOURCE_CSV_URL', '')
        if not csv_url:
            raise CommandError(
                'Chua cau hinh nguon. Dat CHECKLIST_SOURCE_CSV_URL (link CSV Publish to web) hoac truyen --csv-url.'
            )

        try:
            rows = load_csv_rows(csv_url)
        except (requests.RequestException, OSError) as exc:
            raise CommandError(f'Khong doc duoc nguon du lieu: {exc}')

        created = updated = skipped = 0
        for row in rows:
            task_name = pick(row, 'task_name', 'Task_Name', 'Noi_Dung', 'Content', 'Ten_Noi_Dung')
            brand = pick(row, 'brand', 'Brand', 'Thuong_Hieu')
            position = pick(row, 'position', 'Position', 'Vi_Tri')
            if not task_name:
                skipped += 1
                continue
            _, was_created = Checklist.objects.update_or_create(
                tenant=tenant, brand=brand, position=position, task_name=task_name,
                defaults={
                    'day': _to_int(pick(row, 'day', 'Day', 'Ngay'), default=None) or None,
                    'category': pick(row, 'category', 'Category', 'Loai', 'Phan_Loai'),
                    'description': pick(row, 'description', 'Description', 'Mo_Ta'),
                    'doc_url': pick(row, 'doc_url', 'Document_URL', 'Doc_URL', 'Tai_Lieu', 'Link'),
                    'level_group': pick(row, 'level_group', 'Level_Group', 'Nhom_Cap'),
                    'order': _to_int(pick(row, 'order', 'Order', 'STT', 'Thu_Tu'), default=0),
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f'Checklist: {created} tao moi, {updated} cap nhat, {skipped} bo qua (thieu task_name)'
        ))
