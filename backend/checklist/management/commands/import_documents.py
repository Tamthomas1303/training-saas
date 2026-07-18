"""
import_documents — nap tai lieu dao tao that tu Google Sheet (Publish to web > CSV) vao bang Document.
Chay lai khong nhan doi (update_or_create theo tenant + code, hoac tenant + name neu khong co code).

Cot CSV (dung ten, khong phan biet hoa/thuong):
  code, name, file_url, category, brand, position, version, status
  - status: 'done'/'update'/'digitize' hoac 'Hoan thanh'/'Can cap nhat'/'Can so hoa' (mac dinh done).

Nguon: dat DOCUMENTS_SOURCE_CSV_URL (.env / secret) hoac truyen --csv-url.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

import requests

from accounts.models import Tenant
from checklist.models import Document
from config.csv_source import load_csv_rows, pick


def _map_status(raw):
    text = (raw or '').strip().lower()
    if text in ('update', 'can cap nhat', 'cần cập nhật'):
        return Document.Status.UPDATE
    if text in ('digitize', 'can so hoa', 'cần số hóa', 'cần số hoá'):
        return Document.Status.DIGITIZE
    return Document.Status.DONE


class Command(BaseCommand):
    help = 'Nap tai lieu dao tao that tu CSV vao bang Document'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--csv-url', default=None, help='Ghi de DOCUMENTS_SOURCE_CSV_URL')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        csv_url = options['csv_url'] or getattr(settings, 'DOCUMENTS_SOURCE_CSV_URL', '')
        if not csv_url:
            raise CommandError(
                'Chua cau hinh nguon. Dat DOCUMENTS_SOURCE_CSV_URL (link CSV Publish to web) hoac truyen --csv-url.'
            )

        try:
            rows = load_csv_rows(csv_url)
        except (requests.RequestException, OSError) as exc:
            raise CommandError(f'Khong doc duoc nguon du lieu: {exc}')

        created = updated = skipped = 0
        for row in rows:
            name = pick(row, 'name', 'Name', 'Ten', 'Ten_Tai_Lieu', 'Document_Name')
            file_url = pick(row, 'file_url', 'File_URL', 'URL', 'Link', 'Duong_Dan')
            if not file_url:
                # Suy link Google Drive từ Drive_File_ID nếu cột Link để trống (để nút "Xem tài liệu" hiện).
                drive_id = pick(row, 'Drive_File_ID', 'drive_file_id', 'File_ID', 'Drive_ID')
                if drive_id:
                    file_url = f'https://drive.google.com/file/d/{drive_id}/view'
            if not name or not file_url:
                skipped += 1
                continue
            code = pick(row, 'code', 'Code', 'Ma', 'Document_ID')
            defaults = {
                'file_url': file_url,
                'category': pick(row, 'category', 'Category', 'Department', 'Loai', 'Phan_Loai'),
                'brand': pick(row, 'brand', 'Brand', 'Thuong_Hieu'),
                'position': pick(row, 'position', 'Position', 'Vi_Tri'),
                'version': pick(row, 'version', 'Version', 'Phien_Ban') or 'v1.0',
                'status': _map_status(pick(row, 'status', 'Status', 'Trang_Thai')),
            }
            if code:
                _, was_created = Document.objects.update_or_create(
                    tenant=tenant, code=code, defaults={**defaults, 'name': name}
                )
            else:
                _, was_created = Document.objects.update_or_create(
                    tenant=tenant, name=name, defaults=defaults
                )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f'Tai lieu: {created} tao moi, {updated} cap nhat, {skipped} bo qua (thieu name/file_url)'
        ))
