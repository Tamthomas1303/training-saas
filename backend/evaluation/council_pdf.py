"""Sinh PDF tổng hợp Hội đồng đánh giá cấp O (Phase 4). Dùng font VNSans đã đăng ký ở checklist/pdf.py."""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from checklist.pdf import _fetch_image  # noqa: F401 — import để đăng ký font VNSans tiếng Việt


def build_council_pdf(ctx):
    """ctx: title, tenant_name, employee{name,position,restaurant}, kind_label,
    members:[{name,dept_role,result_percent,is_guest}], overall, passed, threshold."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    y = height - margin

    def line(text, size=11, dy=16, bold=False, center=False):
        nonlocal y
        if y < margin + 40:
            c.showPage()
            y = height - margin
        c.setFont('VNSans-Bold' if bold else 'VNSans', size)
        if center:
            c.drawCentredString(width / 2, y, text)
        else:
            c.drawString(margin, y, text)
        y -= dy

    line(ctx['title'], 16, 24, bold=True, center=True)
    line(ctx.get('tenant_name', ''), 10, 20, center=True)
    line(f"Nhân sự: {ctx['employee']['name']} — {ctx['employee']['position']}", 12, 16, bold=True)
    line(f"Nhà hàng: {ctx['employee'].get('restaurant', '')}", 11, 16)
    line(f"Loại đánh giá: {ctx['kind_label']}", 11, 22)

    line('Kết quả từng giám khảo:', 12, 18, bold=True)
    for m in ctx['members']:
        role = f" [{m['dept_role']}]" if m.get('dept_role') else ''
        guest = ' (khách mời)' if m.get('is_guest') else ''
        res = f"{m['result_percent']}%" if m.get('result_percent') is not None else 'Chưa chấm'
        line(f"- {m['name']}{role}{guest}: {res}", 11, 15)

    y -= 8
    verdict = 'ĐẠT' if ctx['passed'] else 'CHƯA ĐẠT'
    line(f"TỔNG HỢP: {ctx['overall']}% — {verdict}  (ngưỡng {ctx['threshold']}%)", 13, 26, bold=True)

    y -= 20
    line('Chủ tịch hội đồng (ký, ghi rõ họ tên): ...........................................', 11, 30)

    c.showPage()
    c.save()
    return buf.getvalue()
