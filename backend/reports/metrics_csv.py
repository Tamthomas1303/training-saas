"""Khoi 3 (To chuc dao tao) + Khoi 4 (Cham dich vu nha hang) cua bao cao dao tao tuan/thang -
doc truc tiep tu Google Sheet (Publish to web > CSV), KHONG qua AI/GPT de tinh so lieu (chi
dung code/csv o day; GPT o services.py CHI viet loi phan tich tu so lieu da tinh san).

Khoi 3 - "To chuc dao tao" (TRAINING_DATA_CSV_URL): moi dong la 1 luot GAN 1 nhan su vao 1
lop, cot: Training_Date, Employee_ID, Employee_Name, Cousera_Code, Cousera_Name, Class_Code,
Learner_Group, Assignment_Status, Participation_Status, Training_Month. Tam thoi dung CSV,
sau nay se noi truc tiep vao du lieu he thong (theo trao doi - da co san phan setup).

Khoi 4 - "Cham dich vu nha hang" (SERVICE_AUDIT_CSV_URL): sheet KHONG co ten cot chuan hoa
nen doc theo VI TRI COT (0-index, A=0): D(3)=ngay cham, F(5)=ten nha hang, I(8)=Score_Criteria,
J(9)=Criteria, N(13)=Result_Score, O(14)=Department_Name. Chi lay dong Department_Name chua
"dao tao" (so khop bo dau). Giu nguon Sheet cho giai doan hien tai - ban thuong mai hoa sau se
bo (theo yeu cau khi lam tinh nang nay).
"""
import csv
import datetime
import io
import unicodedata
from collections import Counter, defaultdict

import requests

DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d')

COL_DATE = 3         # D
COL_RESTAURANT = 5   # F
COL_SCORE_CRITERIA = 8   # I
COL_CRITERIA = 9         # J
COL_RESULT_SCORE = 13    # N
COL_DEPARTMENT = 14      # O

POSITIVE_STATUS_KEYWORDS = ('tham gia', 'dat', 'hoan thanh', 'complete', 'attend', 'present', 'done')
NEGATIVE_STATUS_KEYWORDS = ('khong', 'chua', 'huy', 'xoa', 'cancel', 'remove', 'vang', 'absent', 'miss')


def _no_accent(text):
    s = unicodedata.normalize('NFD', (text or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.lower().replace('đ', 'd')


def _parse_date(value):
    value = (value or '').strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_float(value):
    try:
        return float(str(value or '0').strip().replace(',', '.'))
    except ValueError:
        return None


def _is_assigned_status(text):
    t = _no_accent(text)
    if not t:
        return True
    return not any(k in t for k in NEGATIVE_STATUS_KEYWORDS)


def _is_attended_status(text):
    t = _no_accent(text)
    # Kiem tra tu phu dinh TRUOC - "chua tham gia" chua chinh cum "tham gia" (positive) nen
    # phai loai truong hop nay truoc, khong duoc chi xet positive keyword don thuan.
    if any(k in t for k in NEGATIVE_STATUS_KEYWORDS):
        return False
    return any(k in t for k in POSITIVE_STATUS_KEYWORDS)


def _fetch_csv_dict_rows(csv_url):
    """Doc CSV co dong tieu de ten cot (csv.DictReader) - dung cho sheet 'To chuc dao tao'."""
    resp = requests.get(csv_url, timeout=30)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    return list(csv.DictReader(io.StringIO(resp.text)))


def _fetch_csv_raw_rows(csv_url):
    """Doc CSV theo vi tri cot (bo dong tieu de dau tien) - dung cho sheet 'Cham dich vu'."""
    resp = requests.get(csv_url, timeout=30)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    rows = list(csv.reader(io.StringIO(resp.text)))
    return rows[1:] if rows else []


def training_org_block(csv_url, start, end):
    """Tra ve None neu chua cau hinh TRAINING_DATA_CSV_URL (khoi bi an tren bao cao)."""
    if not csv_url:
        return None
    rows = _fetch_csv_dict_rows(csv_url)

    by_class = defaultdict(lambda: {'name': '', 'assigned': 0, 'attended': 0})
    total_assigned = total_attended = 0
    classes_in_period = set()

    for row in rows:
        d = _parse_date(row.get('Training_Date'))
        if not d or not (start <= d <= end):
            continue
        class_code = (row.get('Class_Code') or '').strip()
        if not class_code:
            continue
        classes_in_period.add(class_code)
        class_name = (row.get('Cousera_Name') or class_code).strip()
        by_class[class_code]['name'] = class_name
        if _is_assigned_status(row.get('Assignment_Status')):
            by_class[class_code]['assigned'] += 1
            total_assigned += 1
        if _is_attended_status(row.get('Participation_Status')):
            by_class[class_code]['attended'] += 1
            total_attended += 1

    classes = []
    for code, data in by_class.items():
        rate = round(data['attended'] / data['assigned'] * 100, 1) if data['assigned'] else 0
        classes.append({
            'code': code, 'name': data['name'], 'assigned': data['assigned'],
            'attended': data['attended'], 'rate': rate,
        })
    classes.sort(key=lambda c: c['name'])

    overall_rate = round(total_attended / total_assigned * 100, 1) if total_assigned else None

    return {
        'total_classes': len(classes_in_period),
        'total_assigned': total_assigned,
        'total_attended': total_attended,
        'overall_rate': overall_rate,
        'classes': classes,
    }


def service_audit_block(csv_url, start, end, kind):
    """Tra ve None neu chua cau hinh SERVICE_AUDIT_CSV_URL. Diem moi nha hang = sum(Result_Score)
    / sum(Score_Criteria) *100 tren cac dong Department_Name chua 'dao tao' + ngay (cot D)
    trong ky. Top van de = Criteria co Result_Score=0, dem tan suat (thang: lap>=2, lay top 5;
    tuan: liet ke het, khong loc nguong)."""
    if not csv_url:
        return None
    rows = _fetch_csv_raw_rows(csv_url)

    by_restaurant = defaultdict(lambda: {'result': 0.0, 'criteria': 0.0})
    zero_score_criteria = Counter()

    for r in rows:
        if len(r) <= COL_DEPARTMENT:
            continue
        if 'dao tao' not in _no_accent(r[COL_DEPARTMENT]):
            continue
        d = _parse_date(r[COL_DATE])
        if not d or not (start <= d <= end):
            continue
        restaurant = (r[COL_RESTAURANT] or '').strip()
        if not restaurant:
            continue
        score_criteria = _parse_float(r[COL_SCORE_CRITERIA])
        result_score = _parse_float(r[COL_RESULT_SCORE])
        if score_criteria is None or result_score is None:
            continue
        by_restaurant[restaurant]['result'] += result_score
        by_restaurant[restaurant]['criteria'] += score_criteria
        if result_score == 0:
            criteria_name = (r[COL_CRITERIA] or '').strip()
            if criteria_name:
                zero_score_criteria[criteria_name] += 1

    restaurants = []
    for name, agg in by_restaurant.items():
        score = round(agg['result'] / agg['criteria'] * 100, 1) if agg['criteria'] else None
        restaurants.append({'restaurant': name, 'score': score})
    restaurants.sort(key=lambda r: (r['score'] is None, r['score']))

    total_result = sum(agg['result'] for agg in by_restaurant.values())
    total_criteria = sum(agg['criteria'] for agg in by_restaurant.values())
    overall_score = round(total_result / total_criteria * 100, 1) if total_criteria else None

    problems = sorted(zero_score_criteria.items(), key=lambda kv: -kv[1])
    if kind == 'month':
        problems = [(name, count) for name, count in problems if count >= 2][:5]
    top_problems = [{'criteria': name, 'count': count} for name, count in problems]

    return {
        'overall_score': overall_score,
        'restaurants': restaurants,
        'top_problems': top_problems,
    }
