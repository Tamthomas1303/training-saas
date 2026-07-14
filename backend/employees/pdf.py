"""Xuat phieu ket qua thu viec (PDF). Port ResultService.gs::generateProbationResultPdf.

Dung lai font/helper da dang ky o checklist.pdf (VNSans) de khong dang ky font 2 lan.
"""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from checklist.pdf import _fetch_image, _placeholder_box  # noqa: F401 (dung chung helper)


def build_probation_result_pdf(ctx):
    """ctx keys: record_no, tenant_name, employee{name,position,restaurant,start_date},
    courses[{name,status}], exams[{name,score}], score_exam, score_practice, score_final,
    final_status, signer_name, signer_title."""
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
    c.drawCentredString(width / 2, y, 'PHIẾU KẾT QUẢ THỬ VIỆC')
    y -= 22
    c.setFont('VNSans', 10)
    c.drawCentredString(width / 2, y, ctx.get('tenant_name', ''))
    y -= 26

    line(f"Số phiếu: {ctx['record_no']}", size=10)
    y -= 6

    line('THÔNG TIN NHÂN SỰ', bold=True, size=12)
    line(f"Họ tên: {ctx['employee'].get('name', '')}")
    line(f"Vị trí: {ctx['employee'].get('position', '')}")
    line(f"Nhà hàng: {ctx['employee'].get('restaurant', '')}")
    line(f"Ngày vào làm: {ctx['employee'].get('start_date', '')}")
    y -= 6

    line('KẾT QUẢ HỌC & THI LMS', bold=True, size=12)
    for course in ctx.get('courses', []):
        line(f"- {course.get('name', '')}: {course.get('status', '')}", size=10)
    for exam in ctx.get('exams', []):
        line(f"- {exam.get('name', '')}: {exam.get('score', '')} điểm", size=10)
    y -= 6

    line('ĐIỂM TỔNG HỢP', bold=True, size=12)
    line(f"Điểm thi lý thuyết: {ctx.get('score_exam', '')}")
    line(f"Điểm thực hành/kỹ năng: {ctx.get('score_practice', '')}")
    line(f"Điểm tổng kết (40% thi + 60% thực hành): {ctx.get('score_final', '')}", bold=True)
    y -= 4
    c.setFillColorRGB(0.18, 0.44, 0.25)
    line(f"Kết quả: {ctx.get('final_status', '')}", bold=True, size=13)
    c.setFillColorRGB(0, 0, 0)
    y -= 20

    sign_w, sign_h = 60 * mm, 25 * mm
    x = margin
    c.setFont('VNSans', 9)
    c.drawString(x, y, ctx.get('signer_title', ''))
    y -= 12
    c.drawString(x, y - sign_h, ctx.get('signer_name', ''))
    _placeholder_box(c, x, y, sign_w, sign_h)

    c.showPage()
    c.save()
    return buf.getvalue()
