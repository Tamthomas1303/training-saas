"""
sync_recruitment — nạp nhân sự mới từ nguồn CSV (Google Sheet Publish to web > CSV).

Thứ tự lấy link: --csv-url > RecruitmentSource (cấu hình trên giao diện) > settings.RECRUITMENT_SOURCE_CSV_URL.
Logic đọc + tạo/cập nhật dùng chung ở employees/recruitment.py (chia sẻ với nút "Đồng bộ ngay"
và endpoint nhập file Excel/CSV).
"""
import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from employees.models import RecruitmentSource
from employees.recruitment import ingest_employees, load_rows_from_url


class Command(BaseCommand):
    help = 'Keo danh sach nhan su moi tu nguon CSV vao bang Employee'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--csv-url', default=None, help='Ghi de link CSV (uu tien cao nhat)')

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        csv_url = options['csv_url']
        if not csv_url:
            src = RecruitmentSource.objects.filter(tenant=tenant).first()
            csv_url = (src.csv_url if src else '') or settings.RECRUITMENT_SOURCE_CSV_URL
        if not csv_url:
            raise CommandError(
                'Chua cau hinh link CSV. Dat tren giao dien (Nhan su > Nguon dong bo) hoac truyen --csv-url.'
            )

        try:
            rows = load_rows_from_url(csv_url)
        except (requests.RequestException, OSError) as exc:
            raise CommandError(f'Khong doc duoc nguon du lieu: {exc}')

        st = ingest_employees(tenant, rows)
        self.stdout.write(self.style.SUCCESS(
            f"Tuyen dung: {st['created']} tao moi, {st['updated']} cap nhat, {st['skipped']} bo qua "
            f"(thieu ma/ten), {st['derived_restaurant']} suy nha hang tu ten, "
            f"{st['unmatched_restaurant']} khong khop nha hang."
        ))
