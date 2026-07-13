"""
Sinh phieu danh gia ky nang (PDF) cho 1 Evaluation da hoan thanh.

Port bo cuc tu PDFService.gs::buildEvaluation (AppsScript Ver 2.0): header + thong tin
nhan su + bang tieu chi (noi dung/diem toi da/diem dat/anh) + dong tong+ket qua + ghi chu +
2 chu ky (nguoi danh gia/nhan vien). Dung chung font tieng Viet (DejaVu Sans) da dang ky
trong checklist/pdf.py.
"""
import textwrap
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from checklist.pdf import _fetch_image, _placeholder_box  # noqa: F401 (dung chung + dang ky font VNSans)


def build_evaluation_pdf(ctx):
    """ctx keys: record_no, tenant_name, eval_type_label, employee{name,position,restaurant,start_date},
    evaluator_name, rows:[{content,max_score,score,photo_url}], total, max, percent, result, note,
    sign_evaluator_url, sign_trainee_url.
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
    c.drawCentredString(width / 2, y, 'PHIẾU ĐÁNH GIÁ KỸ NĂNG')
    y -= 22
    c.setFont('VNSans', 10)
    c.drawCentredString(width / 2, y, f"{ctx.get('tenant_name', '')} · {ctx.get('eval_type_label', '')}")
    y -= 26

    line(f"Số phiếu: {ctx['record_no']}", size=10)
    line(f"Ngày đánh giá: {ctx.get('date', '')}", size=10)
    y -= 6

    line('THÔNG TIN NHÂN SỰ', bold=True, size=12)
    line(f"Họ tên: {ctx['employee'].get('name', '')}")
    line(f"Vị trí: {ctx['employee'].get('position', '')}")
    line(f"Nhà hàng: {ctx['employee'].get('restaurant', '')}")
    line(f"Ngày vào làm: {ctx['employee'].get('start_date', '')}")
    y -= 10

    line('TIÊU CHÍ ĐÁNH GIÁ', bold=True, size=12)

    col_content_x = margin
    col_max_x = margin + 300
    col_score_x = margin + 370
    col_photo_x = margin + 440
    row_h = 18

    c.setFont('VNSans-Bold', 9)
    c.drawString(col_content_x, y, 'Nội dung')
    c.drawCentredString(col_max_x, y, 'Điểm tối đa')
    c.drawCentredString(col_score_x, y, 'Điểm đạt')
    c.drawCentredString(col_photo_x, y, 'Ảnh')
    y -= 4
    c.line(margin, y, width - margin, y)
    y -= row_h

    for idx, row in enumerate(ctx['rows'], start=1):
        if y < 60 * mm:
            c.showPage()
            y = height - margin
        c.setFont('VNSans', 9)
        content = f"{idx}. {row.get('content', '')}"
        wrapped = textwrap.wrap(content, 60) or ['']
        c.drawString(col_content_x, y, wrapped[0])
        c.drawCentredString(col_max_x, y, str(row.get('max_score', '')))
        c.drawCentredString(col_score_x, y, str(row.get('score', '')))

        photo_url = row.get('photo_url')
        if photo_url:
            img = _fetch_image(photo_url)
            if img:
                c.drawImage(
                    img, col_photo_x - 15, y - 10, width=30, height=22,
                    preserveAspectRatio=True, anchor='c',
                )
        rows_used = 1
        for extra in wrapped[1:]:
            y -= row_h
            c.drawString(col_content_x, y, extra)
            rows_used += 1
        y -= row_h

    c.line(margin, y + 10, width - margin, y + 10)
    y -= 6
    c.setFont('VNSans-Bold', 10)
    c.drawString(col_content_x, y, 'Tổng / Kết quả')
    c.drawCentredString(col_max_x, y, str(ctx.get('max', '')))
    c.drawCentredString(col_score_x, y, f"{ctx.get('total', '')} ({ctx.get('percent', 0)}%)")
    result_text = ctx.get('result', '')
    c.setFillColor(colors.HexColor('#1e7a55') if result_text == 'Đạt' else colors.HexColor('#c0392b'))
    c.drawCentredString(col_photo_x, y, result_text)
    c.setFillColor(colors.black)
    y -= 20

    if ctx.get('note'):
        for wrapped_note in textwrap.wrap(f"Ghi chú: {ctx['note']}", 95):
            line(wrapped_note, size=10)
    y -= 10

    line('XÁC NHẬN', bold=True, size=12)
    sign_w, sign_h = 60 * mm, 25 * mm
    gap = 8 * mm
    sign_top = y
    for i, (label, url, name) in enumerate([
        ('Người đánh giá', ctx.get('sign_evaluator_url'), ctx.get('evaluator_name', '')),
        ('Nhân viên', ctx.get('sign_trainee_url'), ctx['employee'].get('name', '')),
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
