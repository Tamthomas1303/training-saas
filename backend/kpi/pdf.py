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

from checklist.pdf import _fetch_image, _placeholder_box, ensure_space


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

    col_no_x = margin
    col_name_x = margin + 30
    col_pos_x = margin + 230
    col_sign_x = margin + 380
    row_h = 46

    # Giu nguyen ven tieu de + dong tieu de cot + it nhat 1 dong chu ky dau tien tren cung 1
    # trang (khong de tieu de "Chu ky" bi mo coi khong con dong nao ben duoi khi sang trang).
    y = ensure_space(c, y, height, margin, 16 + 4 + row_h + 10)
    line('DANH SÁCH THAM GIA & CHỮ KÝ', bold=True, size=12)
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


def _kpi_exclusion_note(row):
    parts = []
    if row.get('excl_resigned'):
        parts.append(f"loại {row['excl_resigned']} nghỉ việc")
    if row.get('excl_next_period'):
        parts.append(f"{row['excl_next_period']} đánh giá kỳ sau")
    return f"({'; '.join(parts)})" if parts else ''


def build_kpi_report_pdf(ctx):
    """ctx keys: record_no, tenant_name, month, year, rows:[{restaurant,brand,on_num,on_den,
    on_rate,skill_pass,skill_total,skill_rate,excl_resigned,excl_next_period}], totals{... +
    excl_resigned,excl_next_period}, am_kcs:[{label,on_rate,skill_rate,restaurant_count}].
    Bao cao KPI BQL theo thang - cong thuc cap nhat theo Apps Script 05-06/08/2026 (xem
    kpi/services.py::_bql_cohort_stats)."""
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
        y -= 12
        note = _kpi_exclusion_note(row)
        if note:
            c.setFont('VNSans', 7)
            c.drawString(col_x[0], y, note[:70])
            c.setFont('VNSans', 9)
            y -= 12
        else:
            y -= 4

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
    y -= 14
    c.setFont('VNSans', 8)
    c.drawString(
        margin, y,
        f"Loại trừ toàn hệ thống: {totals.get('excl_resigned', 0)} nghỉ việc, "
        f"{totals.get('excl_next_period', 0)} đánh giá kỳ sau.",
    )
    y -= 22

    am_kcs = ctx.get('am_kcs') or []
    if am_kcs:
        y = ensure_space(c, y, height, margin, 14 + len(am_kcs) * 14)
        c.setFont('VNSans-Bold', 11)
        c.drawString(margin, y, 'Thống kê theo AM / KCS')
        y -= 16
        c.setFont('VNSans', 9)
        for item in am_kcs:
            c.drawString(
                margin, y,
                f"{item.get('label', '')}: đúng lộ trình TB {item.get('on_rate', 0)}% · "
                f"đạt kỹ năng lần đầu TB {item.get('skill_rate', 0)}% "
                f"({item.get('restaurant_count', 0)} nhà hàng)",
            )
            y -= 14
        y -= 8

    # Giu nguyen ven ghi chu muc tieu + dong nguoi lap (xac nhan) tren cung 1 trang.
    y = ensure_space(c, y, height, margin, 8 + 30 + 9)
    c.setFont('VNSans', 8)
    c.drawString(margin, y, 'Mục tiêu: ≥90% đúng lộ trình, ≥85% đạt kỹ năng lần đầu.')
    y -= 30
    c.setFont('VNSans', 9)
    c.drawString(margin, y, 'Người lập (Phòng Đào tạo)')

    c.showPage()
    c.save()
    return buf.getvalue()


# Khoi ky Phieu phu cap Trainer (Apps Script 05-06/08/2026): thu tu BGD -> Dao tao -> HCNS ->
# Van hanh, moi cot ten phong ban + "(Ky, ghi ro ho ten)" + ten nguoi ky da co san.
ALLOWANCE_SIGNERS = [
    ('Ban Giám đốc', 'Nguyễn Ngọc Diệp - Giám đốc'),
    ('Phòng Đào tạo', 'Nguyễn Văn Tam - Phó phòng Đào tạo'),
    ('Phòng HCNS', 'Nguyễn Thị Mỹ Xuân - Trưởng phòng HCNS'),
    ('Phòng Vận hành', 'Lưu Đức Hiệp - Trưởng phòng Vận hành'),
]


def build_allowance_pdf(ctx):
    """ctx keys: record_no, tenant_name, month, year, rows:[{trainer,trainer_code,
    trainer_restaurant,employee,status,amount}], total_amount. Phieu phu cap trainer."""
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

    headers = ['STT', 'Trainer', 'Mã NV trainer', 'Nhà hàng trainer', 'Nhân sự', 'Trạng thái', 'Số tiền']
    col_x = [margin, margin + 24, margin + 130, margin + 200, margin + 300, margin + 400, margin + 460]
    c.setFont('VNSans-Bold', 8)
    for h, x in zip(headers, col_x):
        c.drawString(x, y, h)
    y -= 4
    c.line(margin, y, width - margin, y)
    y -= 14

    c.setFont('VNSans', 8)
    for idx, row in enumerate(ctx.get('rows', []), start=1):
        if y < 30 * mm:
            c.showPage()
            y = height - margin
            c.setFont('VNSans', 8)
        c.drawString(col_x[0], y, str(idx))
        c.drawString(col_x[1], y, str(row.get('trainer', ''))[:18])
        c.drawString(col_x[2], y, str(row.get('trainer_code', ''))[:14])
        c.drawString(col_x[3], y, str(row.get('trainer_restaurant', ''))[:18])
        c.drawString(col_x[4], y, str(row.get('employee', ''))[:18])
        c.drawString(col_x[5], y, str(row.get('status', '')))
        c.drawString(col_x[6], y, f"{row.get('amount', 0):,.0f}đ")
        y -= 16

    y -= 6
    c.line(margin, y, width - margin, y)
    y -= 18
    c.setFont('VNSans-Bold', 10)
    c.drawString(margin, y, f"Tổng cộng: {ctx.get('total_amount', 0):,.0f}đ")
    y -= 26
    c.setFont('VNSans', 8)
    c.drawString(margin, y, 'Phụ cấp 300.000đ/nhân sự khi đủ 5 điều kiện onboarding.')
    # Giu nguyen ven ca khoi 4 o xac nhan chu ky (ten phong ban + "(Ky...)" + ten) tren cung 1 trang.
    y = ensure_space(c, y, height, margin, 16 + 30 + 40 + 14)
    y -= 20

    col_w = (width - 2 * margin) / len(ALLOWANCE_SIGNERS)
    c.setFont('VNSans-Bold', 9)
    for i, (dept, _name) in enumerate(ALLOWANCE_SIGNERS):
        c.drawCentredString(margin + col_w * i + col_w / 2, y, dept)
    y -= 14
    c.setFont('VNSans', 8)
    for i, _dept in enumerate(ALLOWANCE_SIGNERS):
        c.drawCentredString(margin + col_w * i + col_w / 2, y, '(Ký, ghi rõ họ tên)')
    y -= 45  # khoang trong de ky tay
    c.setFont('VNSans', 9)
    for i, (_dept, name) in enumerate(ALLOWANCE_SIGNERS):
        c.drawCentredString(margin + col_w * i + col_w / 2, y, name)

    c.showPage()
    c.save()
    return buf.getvalue()
