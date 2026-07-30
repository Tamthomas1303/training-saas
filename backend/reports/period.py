"""Tinh khoang ngay (ky) cho bao cao dao tao tuan/thang - dung chung cho ca 4 khoi."""
import datetime


def _last_day_of_month(d):
    if d.month == 12:
        return d.replace(day=31)
    return d.replace(month=d.month + 1, day=1) - datetime.timedelta(days=1)


def compute_period(kind, ref_date=None):
    """kind: 'week' (Thu 2 - CN chua ref_date) hoac 'month' (ngay 1 - cuoi thang chua ref_date).
    Ket qua duoc CAP o ref_date - neu ky chua ket thuc (vd xem bao cao thang giua thang) thi chi
    tinh so lieu TOI NAY, khong tinh truoc cac ngay chua toi. Tra ve (start, end, label)."""
    ref_date = ref_date or datetime.date.today()
    if kind == 'week':
        start = ref_date - datetime.timedelta(days=ref_date.weekday())
        end = start + datetime.timedelta(days=6)
        label = f"Tuần {start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"
    elif kind == 'month':
        start = ref_date.replace(day=1)
        end = _last_day_of_month(ref_date)
        label = f'Tháng {ref_date.month}/{ref_date.year}'
    else:
        raise ValueError(f"kind phai la 'week' hoac 'month', nhan '{kind}'")
    end = min(end, ref_date)
    return start, end, label


def previous_period(kind, start):
    """Ky lien truoc (da ket thuc hoan toan, khong cap) - dung de "so ky truoc" o khoi 4."""
    if kind == 'week':
        return start - datetime.timedelta(days=7), start - datetime.timedelta(days=1)
    prev_last_day = start - datetime.timedelta(days=1)
    return prev_last_day.replace(day=1), prev_last_day
