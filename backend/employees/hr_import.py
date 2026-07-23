"""
hr_import.py — đồng bộ "Auto Syncing - HR Data" (v2.1). Mỗi tab Google Sheet là một nguồn
(HrSyncSource). Roster nhân sự = HỢP (union) nhiều tab, ưu tiên: backup (sau 1/7) > lichsu
(cũ) > lotrinh (cấp S) > bql (cấp O). Lịch sử học/đánh giá nạp ở bước B (hr_history.py).
"""
import csv
import io
import re

import requests
from django.db import transaction

from .models import Employee, HrSyncSource
from .recruitment import (
    _derive_probation_days,
    _map_operation_unit,
    _parse_date,
    restaurant_resolver,
)

# Thứ tự ưu tiên khi hợp nhất roster (điền trước thì giữ).
ROSTER_PRIORITY = ['backup', 'lichsu', 'lotrinh', 'bql']


def load_rows_smart(csv_url, key_header='Employee_ID'):
    """Đọc CSV (link publish-to-web hoặc file), TỰ TÌM dòng tiêu đề chứa key_header (các tab
    Google Sheet thường có vài dòng trống ở đầu)."""
    if csv_url.startswith(('http://', 'https://')):
        resp = requests.get(csv_url, timeout=45)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        text = resp.text
    else:
        with open(csv_url, encoding='utf-8-sig') as fh:
            text = fh.read()
    rows = list(csv.reader(io.StringIO(text)))
    header_idx = None
    for idx, r in enumerate(rows[:20]):
        if any((c or '').strip() == key_header for c in r):
            header_idx = idx
            break
    if header_idx is None:
        return []
    header = [(c or '').strip() for c in rows[header_idx]]
    out = []
    for r in rows[header_idx + 1:]:
        if not any((c or '').strip() for c in r):
            continue
        out.append({header[i]: (r[i] if i < len(r) else '') for i in range(len(header))})
    return out


def _level_group(job_level):
    m = re.match(r'\s*([A-Za-z])', job_level or '')
    return m.group(1).upper() if m else ''


def _map_status(raw):
    return Employee.EmployeeStatus.RESIGNED if 'nghỉ' in (raw or '').lower() else Employee.EmployeeStatus.ACTIVE


def _url_for(tenant, kind):
    src = HrSyncSource.objects.filter(tenant=tenant, kind=kind).first()
    return src.csv_url if (src and src.csv_url) else ''


def _merge_roster_rows(tenant):
    """Đọc các tab liên quan roster, hợp nhất theo Employee_ID (ưu tiên ROSTER_PRIORITY)."""
    merged = {}
    for kind in ROSTER_PRIORITY:
        url = _url_for(tenant, kind)
        if not url:
            continue
        for r in load_rows_smart(url):
            code = (r.get('Employee_ID') or '').strip()
            name = (r.get('Employee_Name') or '').strip()
            if not code or not name:
                continue
            cur = merged.setdefault(code, {})

            def setf(field, value):
                if value and not cur.get(field):
                    cur[field] = value

            setf('name', name)
            setf('position', (r.get('Job_Position') or '').strip())
            # backup dùng cột Level_Group (chữ), các tab khác dùng Job_Level ('S1.2'...).
            setf('job_level', (r.get('Job_Level') or '').strip())
            setf('level_group_raw', (r.get('Level_Group') or '').strip())
            setf('operation_unit', (r.get('Operation_Unit') or '').strip())
            setf('restaurant_name', (r.get('Restaurant_Name') or '').strip())
            setf('restaurant_id', (r.get('Restaurant_ID') or '').strip())
            setf('start_date', (r.get('Start_Date') or '').strip())
            if r.get('Employee_Status') and 'status' not in cur:
                cur['status'] = r.get('Employee_Status')
    return merged


def sync_roster(tenant):
    """Hợp nhất roster từ các tab & upsert Employee (batch, tránh timeout Supabase)."""
    merged = _merge_roster_rows(tenant)
    if not merged:
        return {'total': 0, 'created': 0, 'updated': 0, 'detail': 'Chưa cấu hình link nguồn roster.'}

    resolve_restaurant = restaurant_resolver(tenant)
    existing = {e.code: e for e in Employee.objects.filter(tenant=tenant)}

    to_create, to_update = [], []
    created = updated = 0
    for code, d in merged.items():
        job_level = d.get('job_level', '')
        # nhóm level: ưu tiên Job_Level ('S1.2'→S), fallback Level_Group của backup.
        level_group = _level_group(job_level) or (d.get('level_group_raw', '') or '').upper()[:1]

        restaurant = None
        rid = (d.get('restaurant_id') or '').strip()
        if rid:
            restaurant = Restaurant_by_code(tenant, rid)
        if restaurant is None:
            restaurant = resolve_restaurant(d.get('restaurant_name', ''))

        fields = {
            'name': d.get('name', ''),
            'position': d.get('position', ''),
            'operation_unit': _map_operation_unit(d.get('operation_unit') or d.get('restaurant_name', '')),
            'job_level': job_level,
            'level_group': level_group,
            'start_date': _parse_date(d.get('start_date')),
            'restaurant': restaurant,
            'employee_status': _map_status(d.get('status')),
            'probation_days': _derive_probation_days(
                d.get('position', ''), d.get('operation_unit', ''), job_level,
            ),
        }
        obj = existing.get(code)
        if obj:
            for k, v in fields.items():
                setattr(obj, k, v)
            to_update.append(obj)
            updated += 1
        else:
            to_create.append(Employee(tenant=tenant, code=code, **fields))
            created += 1

    with transaction.atomic():
        if to_create:
            Employee.objects.bulk_create(to_create, batch_size=200)
        if to_update:
            Employee.objects.bulk_update(
                to_update,
                ['name', 'position', 'operation_unit', 'job_level', 'level_group',
                 'start_date', 'restaurant', 'employee_status', 'probation_days'],
                batch_size=200,
            )
    return {'total': len(merged), 'created': created, 'updated': updated}


def Restaurant_by_code(tenant, rid):
    """Khớp nhà hàng theo mã (Restaurant_ID dạng 'KMP-HNO-DTN'); trả None nếu không có."""
    from restaurants.models import Restaurant

    return Restaurant.objects.filter(tenant=tenant, code=rid).first()
