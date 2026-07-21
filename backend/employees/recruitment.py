"""
recruitment.py — logic nạp nhân sự dùng chung cho 3 cách nhập (mục Cách 1/2/3):
  - Lệnh sync_recruitment (CLI / GitHub Actions) — nguồn CSV.
  - Endpoint nhập file (Excel/CSV upload).
  - Endpoint "Đồng bộ ngay" — đọc link CSV lưu trong DB.

Hợp đồng cột (theo DB_Onbroarding): Employee_ID, Employee_Name, Restaurant_Name,
Restaurant_ID (tùy chọn), Job_Position, Operation_Unit, Job_Level, Start_Date, Employee_Status.
"""
import csv
import io
import re
from datetime import datetime

import requests

from employees.models import Employee
from restaurants.models import Restaurant

BRAND_STRIP_RE = re.compile(r'\b(kp|kmp|kampong|yym|yiam|nha hang|nh|pho)\b', re.IGNORECASE)
DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d')


def _normalize_key(value):
    return (value or '').strip().lower()


def _strip_brand(normalized_key):
    return re.sub(r'\s+', ' ', BRAND_STRIP_RE.sub(' ', normalized_key)).strip()


def restaurant_resolver(tenant):
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


def load_rows_from_url(csv_url):
    """Đọc rows từ link (Google Sheet Publish to web > CSV) hoặc đường dẫn file cục bộ."""
    if csv_url.startswith(('http://', 'https://')):
        resp = requests.get(csv_url, timeout=30)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        text = resp.text
    else:
        with open(csv_url, encoding='utf-8-sig') as fh:
            text = fh.read()
    return list(csv.DictReader(io.StringIO(text)))


def load_rows_from_upload(uploaded_file):
    """Đọc rows từ file upload: .xlsx/.xlsm (openpyxl) hoặc .csv."""
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    if name.endswith(('.xlsx', '.xlsm')):
        import openpyxl

        wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        headers = [str(h).strip() if h is not None else '' for h in (next(it, []) or [])]
        rows = []
        for r in it:
            row = {}
            for i, v in enumerate(r):
                if i < len(headers) and headers[i]:
                    row[headers[i]] = '' if v is None else str(v)
            if any(row.values()):
                rows.append(row)
        return rows
    # CSV
    raw = uploaded_file.read()
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8-sig', errors='replace')
    return list(csv.DictReader(io.StringIO(raw)))


def ingest_employees(tenant, rows):
    """Tạo/cập nhật nhân sự từ list[dict]. Trả thống kê. Dùng chung cho cả 3 cách nhập."""
    resolve_restaurant = restaurant_resolver(tenant)
    created = updated = skipped = derived = unmatched = 0

    for row in rows:
        code = (row.get('Employee_ID') or '').strip()
        name = (row.get('Employee_Name') or '').strip()
        if not code or not name:
            skipped += 1
            continue

        restaurant = None
        restaurant_id = (row.get('Restaurant_ID') or '').strip()
        if restaurant_id.isdigit():
            restaurant = Restaurant.objects.filter(tenant=tenant, id=int(restaurant_id)).first()

        restaurant_name = (row.get('Restaurant_Name') or '').strip()
        if restaurant is None and restaurant_name:
            restaurant = resolve_restaurant(restaurant_name)
            if restaurant:
                derived += 1
            else:
                unmatched += 1

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

    return {
        'created': created, 'updated': updated, 'skipped': skipped,
        'derived_restaurant': derived, 'unmatched_restaurant': unmatched,
        'total': len(rows),
    }
