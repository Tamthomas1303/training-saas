"""Khoi 3 (To chuc dao tao) + Khoi 4 (Cham dich vu nha hang) cua bao cao dao tao tuan/thang -
doc truc tiep tu Google Sheet CSV (nen dung endpoint export?format=csv "live", xem
backend/.env.example - link "Publish to web" bi cache CDN tre; du sao van luon them
cache-buster + header no-cache khi goi, xem _fetch_csv_dict_rows/_fetch_csv_raw_rows), KHONG
qua AI/GPT de tinh so lieu (chi dung code/csv o day; GPT o services.py CHI viet loi phan tich
tu so lieu da tinh san).

Khoi 3 - "To chuc dao tao" (TRAINING_DATA_CSV_URL): moi dong la 1 luot GAN 1 nhan su vao 1
lop, cot: Training_Date, Employee_ID, Employee_Name, Cousera_Code, Cousera_Name, Class_Code,
Learner_Group, Assignment_Status, Participation_Status, Training_Month. Tam thoi dung CSV,
sau nay se noi truc tiep vao du lieu he thong (theo trao doi - da co san phan setup).

Khoi 4 - "Cham dich vu nha hang" (SERVICE_AUDIT_CSV_URL): sheet CO dong tieu de ten cot (da
xac nhan qua sheet that ngay 01/08/2026: Assessment_ID, Timestamp, Assessor, Assess_Date,
Restaurant_ID, Restaurant_Name, Brand_Name, Ques_Num, Score_Criteria, Criteria, Category,
Main_Category, Result_Text, Result_Score, Department_Name, Note). Doc theo TEN cot (khong
phan biet hoa/thuong, bo dau) - vi tri cu (D=3,F=5,I=8,J=9,N=13,O=14) chi con la FALLBACK khi
khong tim duoc ten cot tuong ung (sheet cu/khac dinh dang). Chi lay dong Department_Name chua
"dao tao" (so khop bo dau, vd "Phòng Đào tạo"). "Van de" = dong co Result_Text='KHÔNG' (fallback
Result_Score=0 neu sheet khong co cot Result_Text). Giu nguon Sheet cho giai doan hien tai -
ban thuong mai hoa sau se bo (theo yeu cau khi lam tinh nang nay).
"""
import csv
import datetime
import io
import logging
import time
import unicodedata
from collections import Counter, defaultdict

import requests

logger = logging.getLogger(__name__)

DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d')

# Vi tri cot cu (0-index, A=0) - CHI con dung lam FALLBACK khi khong tim duoc ten cot tren
# dong header (xem _find_service_audit_columns). result_text KHONG co vi tri fallback vi la
# cot moi (truoc day khong doc).
COL_DATE = 3         # D
COL_RESTAURANT = 5   # F
COL_SCORE_CRITERIA = 8   # I
COL_CRITERIA = 9         # J
COL_RESULT_SCORE = 13    # N
COL_DEPARTMENT = 14      # O

SERVICE_AUDIT_HEADER_CANDIDATES = {
    'date': ('assess_date', 'ngay_cham', 'date'),
    'restaurant_name': ('restaurant_name',),
    'score_criteria': ('score_criteria',),
    'criteria': ('criteria',),
    'result_text': ('result_text',),
    'result_score': ('result_score',),
    'department_name': ('department_name',),
}
SERVICE_AUDIT_FALLBACK_COL = {
    'date': COL_DATE, 'restaurant_name': COL_RESTAURANT, 'score_criteria': COL_SCORE_CRITERIA,
    'criteria': COL_CRITERIA, 'result_score': COL_RESULT_SCORE, 'department_name': COL_DEPARTMENT,
    'result_text': None,
}

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


def _fetch_csv_dict_rows(csv_url, required_headers=()):
    """Doc CSV co dong tieu de ten cot - dung cho sheet 'To chuc dao tao'. KHONG coi dong DAU
    TIEN la header (csv.DictReader mac dinh) vi sheet nguon co the co vai dong trong/tieu de
    lon truoc dong header that. Thay vao do, TIM dong dau tien chua DU cac ten cot trong
    required_headers roi dung dong do lam fieldnames, du lieu tinh tu dong ke tiep."""
    # Chong cache CDN cua Google "Publish to web" (co the tre vai phut/gio) bang cache-buster
    # theo thoi gian + header no-cache.
    sep = '&' if '?' in csv_url else '?'
    resp = requests.get(
        csv_url + sep + '_cb=' + str(int(time.time())),
        headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'},
        timeout=30,
    )
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    rows = list(csv.reader(io.StringIO(resp.text)))

    header_idx = None
    for i, row in enumerate(rows):
        cells = {(cell or '').strip() for cell in row}
        if all(h in cells for h in required_headers):
            header_idx = i
            break
    if header_idx is None:
        return []

    fieldnames = [(cell or '').strip() for cell in rows[header_idx]]
    data_rows = []
    for row in rows[header_idx + 1:]:
        if not any((cell or '').strip() for cell in row):
            continue  # bo dong trong xen giua
        data_rows.append(dict(zip(fieldnames, row)))
    return data_rows


def _fetch_csv_raw_rows(csv_url):
    """Doc TOAN BO dong CSV (khong bo dong nao) - dung cho sheet 'Cham dich vu'. Dong header co
    the o vi tri bat ky, xem _find_service_audit_columns."""
    sep = '&' if '?' in csv_url else '?'
    resp = requests.get(
        csv_url + sep + '_cb=' + str(int(time.time())),
        headers={'Cache-Control': 'no-cache', 'Pragma': 'no-cache'},
        timeout=30,
    )
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    return list(csv.reader(io.StringIO(resp.text)))


def _find_service_audit_columns(rows):
    """Tim dong header (dong dau tien chua 'Result_Score' hoac 'Department_Name', so khop
    khong phan biet hoa/thuong + bo dau) roi lap map ten cot logic -> vi tri (0-index). Ten
    cot nao khong tim thay tren dong header thi fallback ve vi tri cu
    (SERVICE_AUDIT_FALLBACK_COL) - rieng 'result_text' khong co fallback (None), goi dung
    logic cu (Result_Score=0) khi sheet chua co cot nay.

    Tra ve (header_idx, col_map). header_idx=None neu khong tim duoc dong header nao (ap dung
    toan bo fallback vi tri, giu dung hanh vi truoc khi co ten cot chuan hoa)."""
    header_idx = None
    header_cells_norm = []
    for i, row in enumerate(rows):
        cells_norm = [_no_accent(c) for c in row]
        if 'result_score' in cells_norm or 'department_name' in cells_norm:
            header_idx = i
            header_cells_norm = cells_norm
            break

    col_map = {}
    for logical_name, candidates in SERVICE_AUDIT_HEADER_CANDIDATES.items():
        found = None
        if header_idx is not None:
            for candidate in candidates:
                if candidate in header_cells_norm:
                    found = header_cells_norm.index(candidate)
                    break
        col_map[logical_name] = found if found is not None else SERVICE_AUDIT_FALLBACK_COL[logical_name]
    return header_idx, col_map


def training_org_block(csv_url, start, end):
    """Tra ve None neu chua cau hinh TRAINING_DATA_CSV_URL (khoi bi an tren bao cao)."""
    if not csv_url:
        return None
    rows = _fetch_csv_dict_rows(csv_url, required_headers=('Training_Date', 'Employee_ID'))

    by_class = defaultdict(lambda: {'name': '', 'assigned': 0, 'attended': 0})
    total_assigned = total_attended = 0
    classes_in_period = set()
    rows_in_period = 0

    for row in rows:
        d = _parse_date(row.get('Training_Date'))
        if not d or not (start <= d <= end):
            continue
        rows_in_period += 1
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

    if rows and rows_in_period == 0:
        # Phan biet "sai cau hinh" (URL/header sai -> rows rong) voi "khong co du lieu trong
        # ky" (rows co du lieu nhung khong dong nao roi vao [start..end]) - KHONG doi logic doc.
        logger.info('training_org: doc %s dong, 0 dong trong [%s..%s]', len(rows), start, end)

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
    / sum(Score_Criteria) *100 tren cac dong Department_Name chua 'dao tao' + ngay cham trong
    ky. "Van de" = dong Result_Text='KHÔNG' (fallback Result_Score=0 neu sheet chua co cot
    Result_Text). Top van de: thang - top 5 theo tan suat (KHONG loc nguong >=2 nua); tuan -
    liet ke het."""
    if not csv_url:
        return None
    rows = _fetch_csv_raw_rows(csv_url)
    if not rows:
        return {'overall_score': None, 'restaurants': [], 'top_problems': []}

    header_idx, col = _find_service_audit_columns(rows)
    data_rows = rows[header_idx + 1:] if header_idx is not None else rows[1:]

    by_restaurant = defaultdict(lambda: {'result': 0.0, 'criteria': 0.0})
    failed_criteria = Counter()

    def _cell(row, col_name):
        idx = col[col_name]
        if idx is None or len(row) <= idx:
            return None
        return row[idx]

    for r in data_rows:
        department_name = _cell(r, 'department_name')
        if department_name is None or 'dao tao' not in _no_accent(department_name):
            continue
        date_raw = _cell(r, 'date')
        d = _parse_date(date_raw) if date_raw is not None else None
        if not d or not (start <= d <= end):
            continue
        restaurant = (_cell(r, 'restaurant_name') or '').strip()
        if not restaurant:
            continue
        score_criteria_raw = _cell(r, 'score_criteria')
        result_score_raw = _cell(r, 'result_score')
        if score_criteria_raw is None or result_score_raw is None:
            continue  # dong qua ngan / thieu cot that su - khac voi o trong (0)
        score_criteria = _parse_float(score_criteria_raw)
        result_score = _parse_float(result_score_raw)
        if score_criteria is None or result_score is None:
            continue
        by_restaurant[restaurant]['result'] += result_score
        by_restaurant[restaurant]['criteria'] += score_criteria

        result_text = (_cell(r, 'result_text') or '').strip()
        failed = (result_text.upper() == 'KHÔNG') if result_text else (result_score == 0)
        if failed:
            criteria_name = (_cell(r, 'criteria') or '').strip()
            if criteria_name:
                failed_criteria[criteria_name] += 1

    restaurants = []
    for name, agg in by_restaurant.items():
        score = round(agg['result'] / agg['criteria'] * 100, 1) if agg['criteria'] else None
        restaurants.append({'restaurant': name, 'score': score})
    restaurants.sort(key=lambda r: (r['score'] is None, r['score']))

    total_result = sum(agg['result'] for agg in by_restaurant.values())
    total_criteria = sum(agg['criteria'] for agg in by_restaurant.values())
    overall_score = round(total_result / total_criteria * 100, 1) if total_criteria else None

    problems = sorted(failed_criteria.items(), key=lambda kv: -kv[1])
    if kind == 'month':
        problems = problems[:5]
    top_problems = [{'criteria': name, 'count': count} for name, count in problems]

    return {
        'overall_score': overall_score,
        'restaurants': restaurants,
        'top_problems': top_problems,
    }
