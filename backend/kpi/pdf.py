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


def build_kpi_report_pdf(ctx):
    """ctx keys: record_no, tenant_name, month, year, rows:[{restaurant,brand,on_num,on_den,
    on_rate,skill_pass,skill_total,skill_rate}], totals{...}. Bao cao KPI BQL theo thang."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 15 * mm
    y = height - margin

    c.setFont('VNSans-Bold', 15)
    c.drawCentredString(width / 2, y, f"BÁO CÁO KPI BAN QUẢN LÝ — THÁNG {ctx['month']}/{ctx['year']}")
    y -= 20
    c.setFont('VNSans', 9)
    c.drawCentredString(width / 2, y, ctx.get('tenant_name', ''))
    y -= 24

    headers = ['Nhà hàng', 'Thương hiệu', 'Đúng lộ trình', '%', 'Đạt KN lần đầu', '%']
    col_x = [margin, margin + 130, margin + 220, margin + 300, margin + 340, margin + 430]
    c.setFont('VNSans-Bold', 9)
    for h, x in zip(headers, col_x):
        c.drawString(x, y, h)
    y -= 4
    c.line(margin, y, width - margin, y)
    y -= 14

    c.setFont('VNSans', 9)
    for row in ctx.get('rows', []):
        if y < 30 * mm:
            c.showPage()
            y = height - margin
            c.setFont('VNSans', 9)
        c.drawString(col_x[0], y, str(row.get('restaurant', ''))[:24])
        c.drawString(col_x[1], y, str(row.get('brand', ''))[:16])
        c.drawString(col_x[2], y, f"{row.get('on_num', 0)}/{row.get('on_den', 0)}")
        c.drawString(col_x[3], y, f"{row.get('on_rate', 0)}%")
        c.drawString(col_x[4], y, f"{row.get('skill_pass', 0)}/{row.get('skill_total', 0)}")
        c.drawString(col_x[5], y, f"{row.get('skill_rate', 0)}%")
        y -= 16

    y -= 6
    c.line(margin, y, width - margin, y)
    y -= 18
    totals = ctx.get('totals', {})
    c.setFont('VNSans-Bold', 10)
    c.drawString(
        margin,
        y,
        f"Tổng: {totals.get('on_num', 0)}/{totals.get('on_den', 0)} đúng lộ trình "
        f"({totals.get('on_rate', 0)}%) · {totals.get('skill_pass', 0)}/{totals.get('skill_total', 0)} "
        f"đạt kỹ năng lần đầu ({totals.get('skill_rate', 0)}%)",
    )
    y -= 26
    c.setFont('VNSans', 8)
    c.drawString(margin, y, 'Mục tiêu: ≥90% đúng lộ trình, ≥85% đạt kỹ năng lần đầu.')
    y -= 30
    c.setFont('VNSans', 9)
    c.drawString(margin, y, 'Người lập (Phòng Đào tạo)')

    c.showPage()
    c.save()
    return buf.getvalue()


def build_allowance_pdf(ctx):
    """ctx keys: record_no, tenant_name, month, year, rows:[{trainer,employee,status,amount}],
    total_amount. Phieu phu cap trainer."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 15 * mm
    y = height - margin

    c.setFont('VNSans-Bold', 15)
    c.drawCentredString(width / 2, y, f"PHIẾU PHỤ CẤP TRAINER — THÁNG {ctx['month']}/{ctx['year']}")
    y -= 20
    c.setFont('VNSans', 9)
    c.drawCentredString(width / 2, y, ctx.get('tenant_name', ''))
    y -= 24

    headers = ['STT', 'Trainer', 'Nhân sự', 'Trạng thái', 'Số tiền']
    col_x = [margin, margin + 30, margin + 170, margin + 320, margin + 420]
    c.setFont('VNSans-Bold', 9)
    for h, x in zip(headers, col_x):
        c.drawString(x, y, h)
    y -= 4
    c.line(margin, y, width - margin, y)
    y -= 14

    c.setFont('VNSans', 9)
    for idx, row in enumerate(ctx.get('rows', []), start=1):
        if y < 30 * mm:
            c.showPage()
            y = height - margin
            c.setFont('VNSans', 9)
        c.drawString(col_x[0], y, str(idx))
        c.drawString(col_x[1], y, str(row.get('trainer', ''))[:26])
        c.drawString(col_x[2], y, str(row.get('employee', ''))[:26])
        c.drawString(col_x[3], y, str(row.get('status', '')))
        c.drawString(col_x[4], y, f"{row.get('amount', 0):,.0f}đ")
        y -= 16

    y -= 6
    c.line(margin, y, width - margin, y)
    y -= 18
    c.setFont('VNSans-Bold', 10)
    c.drawString(margin, y, f"Tổng cộng: {ctx.get('total_amount', 0):,.0f}đ")
    y -= 26
    c.setFont('VNSans', 8)
    c.drawString(margin, y, 'Phụ cấp 300.000đ/nhân sự khi đủ 5 điều kiện onboarding.')
    y -= 40

    sign_labels = ['Phòng Đào tạo', 'Ban Giám đốc', 'TP.HCNS', 'TP.Vận hành']
    col_w = (width - 2 * margin) / len(sign_labels)
    c.setFont('VNSans', 9)
    for i, label in enumerate(sign_labels):
        c.drawCentredString(margin + col_w * i + col_w / 2, y, label)

    c.showPage()
    c.save()
    return buf.getvalue()
