"""
Helper doc CSV tu nguon Google Sheet (Publish to web > CSV) hoac file cuc bo.
Dung chung cho cac lenh import_* (nha hang / checklist / tai lieu) — cung co che voi
employees/sync_recruitment.py.
"""
import csv
import io

import requests


def load_csv_rows(csv_url):
    """Tra ve list[dict] tu 1 link CSV (http/https) hoac duong dan file cuc bo."""
    if csv_url.startswith(('http://', 'https://')):
        resp = requests.get(csv_url, timeout=30)
        resp.raise_for_status()
        resp.encoding = 'utf-8'  # Google published CSV luon UTF-8
        text = resp.text
    else:
        with open(csv_url, encoding='utf-8-sig') as fh:
            text = fh.read()
    return list(csv.DictReader(io.StringIO(text)))


def pick(row, *names):
    """Lay gia tri cot dau tien co trong row (bo qua hoa/thuong, khoang trang), tra '' neu khong co."""
    norm = {(k or '').strip().lower(): v for k, v in row.items()}
    for name in names:
        val = norm.get(name.strip().lower())
        if val is not None and str(val).strip() != '':
            return str(val).strip()
    return ''
