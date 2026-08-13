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
        c.setFont('VNSans-Bold' if pos.get('bold') else 'VNSans', pos.get('font_size', 14))
        align = pos.get('align', 'center')
        if align == 'left':
            c.drawString(x, y, value)
        elif align == 'right':
            c.drawRightString(x, y, value)
        else:
            c.drawCentredString(x, y, value)

    c.showPage()
    c.save()
    return buf.getvalue()
