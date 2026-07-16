"""
sync_recruitment — kéo danh sách nhân sự mới từ nguồn tuyển dụng (CSV export) vào bảng Employee.

Nguồn dữ liệu thật (theo AppsScript Ver 2.0/04_HUONG_DAN_DB_Onbroarding.md) là 1 Google Sheet
("DB_Onbroarding") sinh bằng công thức từ sheet tuyển dụng gốc — không có REST API. Cách kết nối
rẻ nhất (0đ, không cần OAuth/service account): Publish to web > CSV trên Google Sheet, rồi cấu hình
link đó vào RECRUITMENT_SOURCE_CSV_URL (.env) hoặc truyền --csv-url. CSV phải có các cột (đúng tên,
theo "hợp đồng tiêu đề" của DB_Onbroarding):
  Employee_ID, Employee_Name, Restaurant_Name, Restaurant_ID (tùy chọn), Job_Position,
  Operation_Unit, Job_Level, Start_Date, Employee_Status

Khi Restaurant_ID trống, nhà hàng được suy ra từ Restaurant_Name — port của
SnapshotService.gs::_restIdResolver: khớp chính xác tên (đã chuẩn hóa) trước, rồi khớp sau khi bỏ
tiền tố thương hiệu/từ chung (kp/kmp/kampong/yym/yiam/"nha hang"/"nh"/"pho").
"""
import csv
import io
import re
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Tenant
from employees.models import Employee
from restaurants.models import Restaurant

BRAND_STRIP_RE = re.compile(r'\b(kp|kmp|kampong|yym|yiam|nha hang|nh|pho)\b', re.IGNORECASE)
DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d')


def _normalize_key(value):
    return (value or '').strip().lower()


def _strip_brand(normalized_key):
    return re.sub(r'\s+', ' ', BRAND_STRIP_RE.sub(' ', normalized_key)).strip()


def _restaurant_resolver(tenant):
    by_exact = {}
    by_stripped = {}
    for restaurant in Restaurant.objects.filter(tenant=tenant):
        key = _normalize_key(restaurant.name)
        if key and key not in by_exact:
            by_exact[key] = restaurant
        stripped = _strip_brand(key)
        if stripped and stripped not in by_stripped:
            by_stripped[stripped] = restaurant

    def resolve(name):
        key = _normalize_key(name)
        if not key:
            return None
        if key in by_exact:
            return by_exact[key]
        return by_stripped.get(_strip_brand(key))

    return resolve


def _parse_date(value):
    value = (value or '').strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _map_operation_unit(raw):
    text = (raw or '').lower()
    if 'sản xuất' in text:
        return Employee.OperationUnit.PRODUCTION
    if 'văn phòng' in text or 'bếp trung tâm' in text:
        return Employee.OperationUnit.OFFICE
    return Employee.OperationUnit.RESTAURANT


def _map_employee_status(raw):
    text = (raw or '').lower()
    if 'nghỉ' in text:
        return Employee.EmployeeStatus.RESIGNED
    if 'thử việc' in text:
        return Employee.EmployeeStatus.PROBATION
    return Employee.EmployeeStatus.ACTIVE


def _derive_probation_days(job_position, operation_unit, job_level):
    position, unit, level = job_position or '', operation_unit or '', (job_level or '').strip().upper()
    if re.search('sản xuất', position, re.IGNORECASE):
        return 0
    if re.search('văn phòng', unit, re.IGNORECASE) or re.search('bếp trung tâm', unit, re.IGNORECASE) or level[:1] == 'O':
        return 60
    return 15


def _load_rows(csv_url):
    if csv_url.startswith(('http://', 'https://')):
        resp = requests.get(csv_url, timeout=30)
        resp.raise_for_status()
        # Google published CSV luon la UTF-8; ep dung UTF-8 de tranh mojibake
        # (requests mac dinh doan ISO-8859-1 khi Content-Type text/csv khong khai bao charset)
        resp.encoding = 'utf-8'
        text = resp.text
    else:
        with open(csv_url, encoding='utf-8-sig') as fh:
            text = fh.read()
    return list(csv.DictReader(io.StringIO(text)))


class Command(BaseCommand):
    help = 'Keo danh sach nhan su moi tu nguon tuyen dung (CSV) vao bang Employee'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='Demo Tenant')
        parser.add_argument('--csv-url', default=None, help='Ghi de RECRUITMENT_SOURCE_CSV_URL trong .env')

    def handle(self, *args, **options):
        csv_url = options['csv_url'] or settings.RECRUITMENT_SOURCE_CSV_URL
        if not csv_url:
            raise CommandError(
                'Chua cau hinh nguon du lieu. Dat RECRUITMENT_SOURCE_CSV_URL trong .env '
                '(link CSV: Google Sheet > File > Share > Publish to web > CSV), hoac truyen --csv-url.'
            )

        tenant = Tenant.objects.filter(name=options['tenant']).first()
        if not tenant:
            raise CommandError(f"Khong tim thay tenant '{options['tenant']}'")

        try:
            rows = _load_rows(csv_url)
        except (requests.RequestException, OSError) as exc:
            raise CommandError(f'Khong doc duoc nguon du lieu: {exc}')

        resolve_restaurant = _restaurant_resolver(tenant)

        created = updated = skipped_no_code = 0
        derived_restaurant = unmatched_restaurant = 0

        for row in rows:
            code = (row.get('Employee_ID') or '').strip()
            name = (row.get('Employee_Name') or '').strip()
            if not code or not name:
                skipped_no_code += 1
                continue

            restaurant = None
            restaurant_id = (row.get('Restaurant_ID') or '').strip()
            if restaurant_id.isdigit():
                restaurant = Restaurant.objects.filter(tenant=tenant, id=int(restaurant_id)).first()

            restaurant_name = (row.get('Restaurant_Name') or '').strip()
            if restaurant is None and restaurant_name:
                restaurant = resolve_restaurant(restaurant_name)
                if restaurant:
                    derived_restaurant += 1
                else:
                    unmatched_restaurant += 1

            job_position = (row.get('Job_Position') or '').strip()
            operation_unit = (row.get('Operation_Unit') or '').strip()
            job_level = (row.get('Job_Level') or '').strip()

            _, was_created = Employee.objects.update_or_create(
                tenant=tenant, code=code,
                defaults={
                    'name': name,
                    'position': job_position,
                    'operation_unit': _map_operation_unit(operation_unit),
                    'job_level': job_level,
                    'start_date': _parse_date(row.get('Start_Date')),
                    'restaurant': restaurant,
                    'employee_status': _map_employee_status(row.get('Employee_Status')),
                    'probation_days': _derive_probation_days(job_position, operation_unit, job_level),
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f'Tuyen dung: {created} tao moi, {updated} cap nhat, {skipped_no_code} bo qua (thieu ma/ten), '
            f'{derived_restaurant} suy ra nha hang tu ten, {unmatched_restaurant} khong khop nha hang nao'
        ))
