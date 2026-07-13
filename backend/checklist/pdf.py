"""
Sinh bien ban dao tao (PDF) cho 1 TrainingProgress da hoan thanh.

Port bo cuc tu PDFService.gs::buildTrainingRecord (AppsScript Ver 2.0): header + thong tin
nhan su + noi dung dao tao + bang 3 anh (Tai lieu/Ly thuyet/Thuc hanh) + bang 2 chu ky
(Trainer/Hoc vien). Dung ReportLab (khong phai WeasyPrint - WeasyPrint can thu vien native
Pango/GObject khong san co tren Windows va kho dam bao tren host free-tier).
"""
import textwrap
from io import BytesIO

import requests
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = settings.BASE_DIR / 'checklist' / 'fonts'
pdfmetrics.registerFont(TTFont('VNSans', str(FONT_DIR / 'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('VNSans-Bold', str(FONT_DIR / 'DejaVuSans-Bold.ttf')))


def _fetch_image(url):
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return ImageReader(BytesIO(resp.content))
    except requests.RequestException:
        return None


def _placeholder_box(c, x, y_top, w, h):
    c.setFillColor(colors.whitesmoke)
    c.rect(x, y_top - h, w, h, fill=1, stroke=1)
    c.setFillColor(colors.black)


def build_training_record_pdf(ctx):
    """ctx keys: record_no, tenant_name, employee{name,position,restaurant,start_date},
    item{name,category,train_date}, trainer_name, note,
    images{tai_lieu,ly_thuyet,thuc_hanh} (URLs), sign_trainer_url, sign_trainee_url.
    Tra ve PDF bytes.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - margin

    def line(text, size=11, dy=16, bold=False):
        nonlocal y
        c.setFont('VNSans-Bold' if bold else 'VNSans', size)
        c.drawString(margin, y, text)
        y -= dy

    c.setFont('VNSans-Bold', 16)
    c.drawCentredString(width / 2, y, 'BIÊN BẢN ĐÀO TẠO NHÂN SỰ')
    y -= 22
    c.setFont('VNSans', 10)
    c.drawCentredString(width / 2, y, ctx.get('tenant_name', ''))
    y -= 26

    line(f"Số biên bản: {ctx['record_no']}", size=10)
    line(f"Ngày đào tạo: {ctx['item'].get('train_date', '')}", size=10)
    y -= 6

    line('THÔNG TIN NHÂN SỰ', bold=True, size=12)
    line(f"Họ tên: {ctx['employee'].get('name', '')}")
    line(f"Vị trí: {ctx['employee'].get('position', '')}")
    line(f"Nhà hàng: {ctx['employee'].get('restaurant', '')}")
    line(f"Ngày vào làm: {ctx['employee'].get('start_date', '')}")
    y -= 6

    line('NỘI DUNG ĐÀO TẠO', bold=True, size=12)
    category = ctx['item'].get('category') or ''
    suffix = f' ({category})' if category else ''
    line(f"{ctx['item'].get('name', '')}{suffix}")
    if ctx.get('note'):
        for wrapped in textwrap.wrap(f"Ghi chú: {ctx['note']}", 95):
            line(wrapped, size=10)
    y -= 10

    line('HÌNH ẢNH MINH CHỨNG BUỔI ĐÀO TẠO', bold=True, size=12)
    photo_w, photo_h = 50 * mm, 37 * mm
    gap = 8 * mm
    x = margin
    photo_top = y
    for label, url in [
        ('Tài liệu', ctx['images'].get('tai_lieu')),
        ('Lý thuyết', ctx['images'].get('ly_thuyet')),
        ('Thực hành', ctx['images'].get('thuc_hanh')),
    ]:
        img = _fetch_image(url)
        if img:
            c.drawImage(
                img, x, photo_top - photo_h, width=photo_w, height=photo_h,
                preserveAspectRatio=True, anchor='c',
            )
        else:
            _placeholder_box(c, x, photo_top, photo_w, photo_h)
        c.setFont('VNSans', 9)
        c.drawCentredString(x + photo_w / 2, photo_top - photo_h - 12, label)
        x += photo_w + gap
    y = photo_top - photo_h - 26

    line('XÁC NHẬN', bold=True, size=12)
    sign_w, sign_h = 60 * mm, 25 * mm
    sign_top = y
    for i, (label, url, name) in enumerate([
        ('Người đào tạo (Trainer)', ctx.get('sign_trainer_url'), ctx.get('trainer_name', '')),
        ('Học viên', ctx.get('sign_trainee_url'), ctx['employee'].get('name', '')),
    ]):
        x = margin + i * (sign_w + gap)
        img = _fetch_image(url)
        if img:
            c.drawImage(
                img, x, sign_top - sign_h, width=sign_w, height=sign_h,
                preserveAspectRatio=True, anchor='c',
            )
        else:
            _placeholder_box(c, x, sign_top, sign_w, sign_h)
        c.setFont('VNSans', 9)
        c.drawCentredString(x + sign_w / 2, sign_top - sign_h - 12, label)
        c.drawCentredString(x + sign_w / 2, sign_top - sign_h - 24, name)

    c.showPage()
    c.save()
    return buf.getvalue()
