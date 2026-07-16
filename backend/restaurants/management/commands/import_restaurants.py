"""
import_restaurants — nap danh sach nha hang that tu 1 Google Sheet (Publish to web > CSV)
vao bang Restaurant. Chay lai khong nhan doi (update_or_create theo tenant + code).

Cot CSV (dung ten, khong phan biet hoa/thuong):
  code, name, brand, city, district, region, email, status
  - status: 'active'/'inactive' hoac 'Dang hoat dong'/'Ngung hoat dong' (mac dinh active).

Nguon: dat RESTAURANTS_SOURCE_CSV_URL (.env / secret) hoac truyen --csv-url.
Them --clear-sample de xoa 3 nha hang mau (NH001, NH002, NH003) do seed_sample_data tao.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import requests

from accounts.models import Tenant
from config.csv_source import load_csv_rows, pick
from restaurants.models import Restaurant

SAMPLE_CODES = ('NH001', 'NH002', 'NH003')


def _map_status(raw):
    text = (raw or '').strip().lower()
    if text in ('inactive', 'ngung hoat dong', 'ngừng hoạt động', 'ngưng hoạt động', 'off'):
        return Restaurant.Status.INACTIVE
    return Restaurant.Status.ACTIVE


class Command(BaseCommand):
    help = 'Nap nha hang that tu CSV vao bang Restaurant'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--csv-url', default=None, help='Ghi de RESTAURANTS_SOURCE_CSV_URL')
        parser.add_argument('--clear-sample', action='store_true', help='Xoa 3 nha hang mau NH001-003')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        if options['clear_sample']:
            deleted, _ = Restaurant.objects.filter(tenant=tenant, code__in=SAMPLE_CODES).delete()
            self.stdout.write(self.style.WARNING(f'Da xoa {deleted} ban ghi nha hang mau (NH001-003)'))

        csv_url = options['csv_url'] or getattr(settings, 'RESTAURANTS_SOURCE_CSV_URL', '')
        if not csv_url:
            raise CommandError(
                'Chua cau hinh nguon. Dat RESTAURANTS_SOURCE_CSV_URL (link CSV Publish to web) '
                'hoac truyen --csv-url. (Neu chi muon xoa mau thi dung --clear-sample rieng.)'
            )

        try:
            rows = load_csv_rows(csv_url)
        except (requests.RequestException, OSError) as exc:
            raise CommandError(f'Khong doc duoc nguon du lieu: {exc}')

        created = updated = skipped = 0
        for row in rows:
            code = pick(row, 'code', 'Restaurant_ID', 'Ma', 'Ma_Nha_Hang')
            name = pick(row, 'name', 'Restaurant_Name', 'Ten', 'Ten_Nha_Hang')
            if not code or not name:
                skipped += 1
                continue
            _, was_created = Restaurant.objects.update_or_create(
                tenant=tenant, code=code,
                defaults={
                    'name': name,
                    'brand': pick(row, 'brand', 'Brand', 'Brand_Name', 'Thuong_Hieu'),
                    'city': pick(row, 'city', 'City', 'Thanh_Pho', 'Tinh'),
                    'district': pick(row, 'district', 'District', 'Quan_Huyen', 'Quan'),
                    'region': pick(row, 'region', 'Region', 'Khu_Vuc', 'Vung'),
                    'email': pick(row, 'email', 'Email', 'Restaurant_Mail'),
                    'status': _map_status(pick(row, 'status', 'Restaurant_Status', 'Trang_Thai')),
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f'Nha hang: {created} tao moi, {updated} cap nhat, {skipped} bo qua (thieu code/name)'
        ))
