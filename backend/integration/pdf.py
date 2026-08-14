"""
Sinh PDF chung chi (Dot 3 phan D): overlay chu (ten nguoi nhan/khoa-chuong trinh/dong loai/ngay
cap+ma) len ANH NEN mau admin upload (CertificateTemplate.template_pdf_url), dung canvas ve
truc tiep giong employees.pdf::build_levelup_proposal_pdf (toa do tu do, khong phai bang), khong
dung bo Platypus (khong hop voi kieu "phu kin trang bang 1 anh").

Khong dang ky lai font VNSans (dang ky 1 lan o checklist.pdf, dung chung).
"""
from io import BytesIO

from reportlab.pdfgen import canvas

from checklist.pdf import _fetch_image

CERT_WIDTH = 853
CERT_HEIGHT = 603
_EDGE_MARGIN = 24  # chừa mép để chữ dài không chạm viền


def _fit_font_size(c, text, font, size, x, align):
    """Tự thu nhỏ cỡ chữ để chuỗi KHÔNG tràn ra ngoài mép trang, tính theo điểm neo + kiểu căn.
    Trả về cỡ chữ đã điều chỉnh (không phóng to, chỉ thu nhỏ; tối thiểu 6pt)."""
    if align == 'left':
        avail = CERT_WIDTH - x - _EDGE_MARGIN
    elif align == 'right':
        avail = x - _EDGE_MARGIN
    else:  # center: giới hạn bởi mép gần hơn để cân 2 bên
        avail = 2 * min(x, CERT_WIDTH - x) - _EDGE_MARGIN
    if avail <= 0:
        return size
    width = c.stringWidth(text, font, size)
    if width <= avail:
        return size
    return max(6, size * avail / width)


def build_certificate_pdf(template, fields):
    """template: CertificateTemplate. fields: {recipient_name, program_or_course_name,
    completion_line, issue_date, cert_code} (gia tri str, bo qua field rong/None)."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(CERT_WIDTH, CERT_HEIGHT))

    bg = _fetch_image(template.template_pdf_url)
    if bg:
        c.drawImage(bg, 0, 0, width=CERT_WIDTH, height=CERT_HEIGHT, preserveAspectRatio=False)

    config = template.fields_config or {}
    for key, value in fields.items():
        if not value:
            continue
        pos = config.get(key)
        if not pos:
            continue
        x, y = pos.get('x', CERT_WIDTH / 2), pos.get('y', CERT_HEIGHT / 2)
        align = pos.get('align', 'center')
        font = 'VNSans-Bold' if pos.get('bold') else 'VNSans'
        size = _fit_font_size(c, value, font, pos.get('font_size', 14), x, align)
        c.setFont(font, size)
        if align == 'left':
            c.drawString(x, y, value)
        elif align == 'right':
            c.drawRightString(x, y, value)
        else:
            c.drawCentredString(x, y, value)

    c.showPage()
    c.save()
    return buf.getvalue()
