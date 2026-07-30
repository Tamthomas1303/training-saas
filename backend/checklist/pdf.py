"""
Sinh bien ban dao tao (PDF) cho 1 TrainingProgress da hoan thanh.

Port bo cuc tu PDFService.gs::buildTrainingRecord (AppsScript Ver 2.0): header + thong tin
nhan su + noi dung dao tao + bang 3 anh (Tai lieu/Ly thuyet/Thuc hanh) + bang 2 chu ky
(Trainer/Hoc vien). Dung ReportLab (khong phai WeasyPrint - da thu va xac nhan WeasyPrint
can thu vien native Pango/GObject/Cairo khong cai duoc qua pip, khong chay duoc tren may dev
Windows lan Render voi cach deploy buildpack thuan Python hien tai - xem quyet dinh trong
sprint "PDF thiet ke lai").

File nay co 2 bo helper:
  - Ham dung canvas.Canvas ve truc tiep (_fetch_image, _placeholder_box, ensure_space) - van
    dung boi kpi/pdf.py va 2 ham con lai cua employees/pdf.py (chua thiet ke lai dot nay).
  - Bo "kit" Platypus (pdf_styles, styled_table, platypus_image, pdf_header_block) - dung
    boi build_training_record_pdf (file nay), evaluation/pdf.py::build_evaluation_pdf,
    employees/pdf.py::build_probation_result_pdf - bang co vien/mau nen tieu de/padding
    giong CSS chuan, KeepTogether cho khoi chu ky, dep hon nhieu so voi ve tung dong bang
    canvas.drawString.
"""
from io import BytesIO

import requests
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

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


def ensure_space(c, y, page_height, margin, needed):
    """Neu khong du 'needed' diem truc-y con lai tren trang hien tai thi sang trang moi
    TRUOC KHI ve, roi tra ve y moi (= page_height - margin). Goi truoc khi bat dau ve 1 khoi
    can giu nguyen ven (vd bang/section chua o chu ky) voi 'needed' la tong chieu cao that su
    cua khoi do - tuong duong KeepTogether cua ReportLab Platypus nhung dung duoc voi
    canvas.Canvas (ve truc tiep, khong flowable) nhu kpi/pdf.py va 2 ham con lai cua
    employees/pdf.py (chua chuyen sang Platypus)."""
    if y - needed < margin:
        c.showPage()
        return page_height - margin
    return y


# ---------------------------------------------------------------------------
# Platypus "kit" dung chung cho 3 phieu thiet ke lai (bang dep, chu ky KeepTogether).
# Mau/kich thuoc tuong duong CSS chuan: border #cfd6d3, header nen #eef3f1, chu #222,
# muted #666, tieu de #1e6f5c.
# ---------------------------------------------------------------------------
COLOR_PRIMARY = colors.HexColor('#1e6f5c')
COLOR_TEXT = colors.HexColor('#222222')
COLOR_MUTED = colors.HexColor('#666666')
COLOR_BORDER = colors.HexColor('#cfd6d3')
COLOR_HEADER_BG = colors.HexColor('#eef3f1')
PAGE_MARGIN = 18 * mm


def pdf_styles():
    """Cac ParagraphStyle dung chung - goi 1 lan moi ham build_*_pdf (ParagraphStyle khong
    dung lai duoc giua cac lan build vi Platypus co the mutate state)."""
    return {
        'h2': ParagraphStyle(
            'h2', fontName='VNSans-Bold', fontSize=17, textColor=COLOR_PRIMARY,
            leading=20, spaceAfter=2,
        ),
        'muted': ParagraphStyle('muted', fontName='VNSans', fontSize=9, textColor=COLOR_MUTED, leading=12),
        'muted_right': ParagraphStyle(
            'muted_right', fontName='VNSans', fontSize=9, textColor=COLOR_MUTED, leading=13, alignment=2,
        ),
        'h3': ParagraphStyle(
            'h3', fontName='VNSans-Bold', fontSize=12, textColor=COLOR_TEXT,
            leading=15, spaceBefore=12, spaceAfter=5,
        ),
        'body': ParagraphStyle('body', fontName='VNSans', fontSize=10, textColor=COLOR_TEXT, leading=14),
        'body_bold': ParagraphStyle('body_bold', fontName='VNSans-Bold', fontSize=10, textColor=COLOR_TEXT, leading=14),
        'cell': ParagraphStyle('cell', fontName='VNSans', fontSize=9, textColor=COLOR_TEXT, leading=12),
        'cell_bold': ParagraphStyle('cell_bold', fontName='VNSans-Bold', fontSize=9, textColor=COLOR_TEXT, leading=12),
        'cell_center': ParagraphStyle(
            'cell_center', fontName='VNSans', fontSize=9, textColor=COLOR_TEXT, leading=12, alignment=1,
        ),
        'cell_bold_center': ParagraphStyle(
            'cell_bold_center', fontName='VNSans-Bold', fontSize=9, textColor=COLOR_TEXT, leading=12, alignment=1,
        ),
        'result_pass': ParagraphStyle(
            'result_pass', fontName='VNSans-Bold', fontSize=12, textColor=COLOR_PRIMARY, leading=16,
        ),
        'result_fail': ParagraphStyle(
            'result_fail', fontName='VNSans-Bold', fontSize=12, textColor=colors.HexColor('#c0392b'), leading=16,
        ),
        'caption': ParagraphStyle('caption', fontName='VNSans', fontSize=9, textColor=COLOR_TEXT, leading=12, alignment=1),
    }


def styled_table(data, col_widths=None, header=True, row_heights=None):
    """Bang chuan cho ca 3 phieu: vien 0.75pt mau #cfd6d3, header nen #eef3f1 chu dam,
    padding 6x8, canh tren - tuong duong CSS 'table/th/td' trong yeu cau."""
    style_cmds = [
        ('GRID', (0, 0), (-1, -1), 0.75, COLOR_BORDER),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    if header:
        style_cmds.append(('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG))
    table = Table(data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1 if header else 0)
    table.setStyle(TableStyle(style_cmds))
    return table


def platypus_image(url, w, h):
    """Tai anh tu URL public (vd Cloudflare R2) lam Platypus Image; neu loi/khong co URL thi
    tra ve 1 o trong co vien (khong lam hong bo cuc bang)."""
    if url:
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            img = Image(BytesIO(resp.content), width=w, height=h)
            img.hAlign = 'CENTER'
            return img
        except Exception:
            pass
    placeholder = Table([['']], colWidths=[w], rowHeights=[h])
    placeholder.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, COLOR_BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
    ]))
    placeholder.hAlign = 'CENTER'
    return placeholder


def pdf_header_block(title, tenant_name, right_lines, styles):
    """Khoi '.hd': trai la <h2>title</h2> + tenant_name (muted), phai la cac dong muted
    (vd 'So: ...' / 'Ngay: ...'), gach chan day 2pt mau #1e6f5c ben duoi ca khoi."""
    left = [Paragraph(title, styles['h2']), Paragraph(tenant_name or '', styles['muted'])]
    right = [Paragraph(line, styles['muted_right']) for line in right_lines]
    header_table = Table([[left, right]], colWidths=[None, 60 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 2, COLOR_PRIMARY),
    ]))
    return header_table


def build_training_record_pdf(ctx):
    """ctx keys: record_no, tenant_name, employee{name,position,restaurant,start_date},
    item{name,category,train_date}, trainer_name, note,
    images{tai_lieu,ly_thuyet,thuc_hanh} (URLs), sign_trainer_url, sign_trainee_url.
    Tra ve PDF bytes. Dung Platypus (SimpleDocTemplate + Table/Paragraph) - bang co vien,
    header nen, padding chuan; khoi ".sign" boc KeepTogether de khong bi tach qua trang."""
    from reportlab.platypus import SimpleDocTemplate

    styles = pdf_styles()
    story = []

    emp = ctx.get('employee', {})
    item = ctx.get('item', {})
    story.append(pdf_header_block(
        'BIÊN BẢN ĐÀO TẠO NHÂN SỰ', ctx.get('tenant_name', ''),
        [f"Số: {ctx['record_no']}", f"Ngày: {item.get('train_date', '')}"], styles,
    ))
    story.append(Spacer(1, 10))

    story.append(styled_table(
        [
            [Paragraph('Họ tên', styles['cell_bold']), Paragraph(emp.get('name', ''), styles['cell']),
             Paragraph('Vị trí', styles['cell_bold']), Paragraph(emp.get('position', ''), styles['cell'])],
            [Paragraph('Nhà hàng', styles['cell_bold']), Paragraph(emp.get('restaurant', ''), styles['cell']),
             Paragraph('Ngày vào làm', styles['cell_bold']), Paragraph(emp.get('start_date', ''), styles['cell'])],
        ],
        col_widths=[28 * mm, 62 * mm, 28 * mm, 56 * mm], header=False,
    ))

    story.append(Paragraph('NỘI DUNG ĐÀO TẠO', styles['h3']))
    category = item.get('category') or ''
    suffix = f' ({category})' if category else ''
    story.append(Paragraph(f"{item.get('name', '')}{suffix}", styles['body']))
    if ctx.get('note'):
        story.append(Paragraph(f"Ghi chú: {ctx['note']}", styles['body']))

    story.append(Paragraph('HÌNH ẢNH MINH CHỨNG BUỔI ĐÀO TẠO', styles['h3']))
    images = ctx.get('images', {})
    photo_w, photo_h = 150, 110
    story.append(styled_table(
        [
            [Paragraph('Tài liệu', styles['cell_bold']), Paragraph('Lý thuyết', styles['cell_bold']),
             Paragraph('Thực hành', styles['cell_bold'])],
            [
                platypus_image(images.get('tai_lieu'), photo_w, photo_h),
                platypus_image(images.get('ly_thuyet'), photo_w, photo_h),
                platypus_image(images.get('thuc_hanh'), photo_w, photo_h),
            ],
        ],
        col_widths=[None, None, None],
    ))

    sign_w, sign_h = 200, 90
    sign_block = [
        Paragraph('XÁC NHẬN', styles['h3']),
        styled_table(
            [
                [Paragraph('Người đào tạo (Trainer)', styles['cell_bold']), Paragraph('Học viên', styles['cell_bold'])],
                [
                    platypus_image(ctx.get('sign_trainer_url'), sign_w, sign_h),
                    platypus_image(ctx.get('sign_trainee_url'), sign_w, sign_h),
                ],
                [Paragraph(ctx.get('trainer_name', ''), styles['caption']), Paragraph(emp.get('name', ''), styles['caption'])],
            ],
            col_widths=[None, None], header=False,
        ),
    ]
    story.append(KeepTogether(sign_block))

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN, bottomMargin=PAGE_MARGIN,
    )
    doc.build(story)
    return buf.getvalue()
