"""
Sinh bien ban buoi dao tao KPI (PDF). Port PDFService.gs::buildKpiSession: header + thong tin
chu de/nguoi dao tao/nha hang + bang 3 anh (tai lieu/ly thuyet/thuc hanh) + bang danh sach
tham gia (moi nguoi 1 dong: STT, ho ten, vi tri, chu ky rieng). Dung chung font DejaVu voi
bien ban dao tao / phieu danh gia.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from checklist.pdf import _fetch_image, _placeholder_box  # noqa: F401 (dang ky font VNSans)


def build_kpi_session_pdf(ctx):
    """ctx keys: record_no, tenant_name, restaurant, topic, date, trainer_name,
    images{tai_lieu,ly_thuyet,thuc_hanh}, participants:[{name,position,sign_url}].
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
    c.drawCentredString(width / 2, y, 'BIÊN BẢN BUỔI ĐÀO TẠO (KPI)')
    y -= 22
    c.setFont('VNSans', 10)
    c.drawCentredString(width / 2, y, ctx.get('tenant_name', ''))
    y -= 26

    line(f"Số biên bản: {ctx['record_no']}", size=10)
    line(f"Ngày: {ctx.get('date', '')}", size=10)
    y -= 6

    line('THÔNG TIN BUỔI ĐÀO TẠO', bold=True, size=12)
    line(f"Chủ đề: {ctx.get('topic', '')}")
    line(f"Người đào tạo: {ctx.get('trainer_name', '')}")
    line(f"Nhà hàng: {ctx.get('restaurant', '')}")
    line(f"Số người tham gia: {len(ctx.get('participants', []))}")
    y -= 10

    line('HÌNH ẢNH MINH CHỨNG', bold=True, size=12)
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

    line('DANH SÁCH THAM GIA & CHỮ KÝ', bold=True, size=12)
    col_no_x = margin
    col_name_x = margin + 30
    col_pos_x = margin + 230
    col_sign_x = margin + 380
    row_h = 46

    c.setFont('VNSans-Bold', 9)
    c.drawString(col_no_x, y, 'STT')
    c.drawString(col_name_x, y, 'Họ tên')
    c.drawString(col_pos_x, y, 'Vị trí')
    c.drawString(col_sign_x, y, 'Chữ ký')
    y -= 4
    c.line(margin, y, width - margin, y)
    y -= row_h

    for idx, p in enumerate(ctx.get('participants', []), start=1):
        if y < 30 * mm:
            c.showPage()
            y = height - margin
        c.setFont('VNSans', 9)
        c.drawString(col_no_x, y + row_h - 30, str(idx))
        c.drawString(col_name_x, y + row_h - 30, p.get('name', ''))
        c.drawString(col_pos_x, y + row_h - 30, p.get('position', ''))
        img = _fetch_image(p.get('sign_url'))
        sign_w, sign_h = 80, 32
        if img:
            c.drawImage(
                img, col_sign_x, y + row_h - 30 - sign_h + 8, width=sign_w, height=sign_h,
                preserveAspectRatio=True, anchor='c',
            )
        else:
            c.setFillColor(colors.whitesmoke)
            c.rect(col_sign_x, y + row_h - 30 - sign_h + 8, sign_w, sign_h, fill=1, stroke=1)
            c.setFillColor(colors.black)
        c.line(margin, y, width - margin, y)
        y -= row_h

    c.showPage()
    c.save()
    return buf.getvalue()
