"""
Sinh bien ban buoi dao tao KPI (PDF). Port PDFService.gs::buildKpiSession: header + thong tin
chu de/nguoi dao tao/nha hang + bang 3 anh (tai lieu/ly thuyet/thuc hanh) + bang danh sach
tham gia (moi nguoi 1 dong: STT, ho ten, vi tri, chu ky rieng). Dung chung font DejaVu voi
bien ban dao tao / phieu danh gia.

build_kpi_session_pdf van dung canvas.Canvas ve truc tiep (chua thiet ke lai dot nay).
build_kpi_report_pdf/build_allowance_pdf da chuyen sang bo "kit" Platypus (xem checklist/
pdf.py) - Phan 3, Prompt_v2.1_Port_va_LamDep_Form_07.08.2026.md: lam dep 2 form nay giong
ban Apps Script (H2 xanh #1e6f5c, header gach chan 2pt, bang vien manh #cfd6d3, dong TONG in
dam, khoi ky khong bi cat qua trang). KHONG chuyen sang WeasyPrint nhu ghi chu cua prompt goi
y - da thu WeasyPrint truoc do va xac nhan can thu vien native Pango/GObject/Cairo khong cai
duoc qua pip tren may dev Windows lan Render (xem checklist/pdf.py docstring); bo kit Platypus
san co da dung DUNG bang mau/vien nay roi nen dung lai la lua chon nhat quan hon.
"""
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from checklist.pdf import (
    PAGE_MARGIN, _fetch_image, _placeholder_box, ensure_space, pdf_header_block, pdf_styles,
    styled_table,
)


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


def _rate_or_dash(denominator, rate):
    """Ty le hien '—' khi mau so = 0 (thay vi '0%' gay hieu nham) - Phan 3 muc 3.1."""
    return f'{rate}%' if denominator else '—'


def _format_vnd(amount):
    """300000 -> '300.000đ' (dau cham phan cach hang nghin kieu VN, khac dau phay mac dinh cua
    Python) - Phan 3 muc 3.2."""
    return f"{amount:,.0f}".replace(',', '.') + 'đ'


def build_kpi_report_pdf(ctx):
    """ctx keys: record_no, tenant_name, month, year, generated, rows:[{restaurant,brand,
    on_num,on_den,on_rate,skill_pass,skill_total,skill_rate,excl_resigned,excl_next_period}],
    totals{... + excl_resigned,excl_next_period}, am_kcs:[{role,name,scope,emp_count,on_num,
    on_den,on_rate,skill_pass,skill_total,skill_rate}]. Bao cao KPI BQL theo thang - cong thuc
    + giao dien cap nhat theo Apps Script 05-07/08/2026 (xem kpi/services.py::_bql_cohort_stats,
    _kpi_bql_am_kcs_om_stats)."""
    styles = pdf_styles()
    story = []
    month, year = ctx['month'], ctx['year']

    story.append(pdf_header_block(
        'BÁO CÁO KPI ĐÀO TẠO — BAN QUẢN LÝ NHÀ HÀNG',
        f"{ctx.get('tenant_name', '')} · Kỳ: Tháng {month}/{year}",
        [f"Ngày lập: {ctx.get('generated', '')}"], styles,
    ))
    story.append(Spacer(1, 10))

    note_style = ParagraphStyle(
        'kpi_excl_note', fontName='VNSans', fontSize=8, textColor=colors.HexColor('#b06a00'), leading=10,
    )
    rows_data = [[
        Paragraph('STT', styles['cell_bold_center']), Paragraph('Nhà hàng', styles['cell_bold']),
        Paragraph('Thương hiệu', styles['cell_bold_center']),
        Paragraph('NV đúng lộ trình', styles['cell_bold_center']), Paragraph('Tỷ lệ', styles['cell_bold_center']),
        Paragraph('Đạt kỹ năng lần đầu', styles['cell_bold_center']), Paragraph('Tỷ lệ', styles['cell_bold_center']),
    ]]
    for idx, row in enumerate(ctx.get('rows', []), start=1):
        restaurant_cell = [Paragraph(row.get('restaurant', ''), styles['cell'])]
        note = _kpi_exclusion_note(row)
        if note:
            restaurant_cell.append(Paragraph(note, note_style))
        rows_data.append([
            Paragraph(str(idx), styles['cell_center']), restaurant_cell,
            Paragraph(row.get('brand', ''), styles['cell_center']),
            Paragraph(f"{row.get('on_num', 0)}/{row.get('on_den', 0)}", styles['cell_center']),
            Paragraph(_rate_or_dash(row.get('on_den', 0), row.get('on_rate', 0)), styles['cell_center']),
            Paragraph(f"{row.get('skill_pass', 0)}/{row.get('skill_total', 0)}", styles['cell_center']),
            Paragraph(_rate_or_dash(row.get('skill_total', 0), row.get('skill_rate', 0)), styles['cell_center']),
        ])

    totals = ctx.get('totals', {})
    total_row_idx = len(rows_data)
    rows_data.append([
        Paragraph('TỔNG', styles['cell_bold_center']), '', '',
        Paragraph(f"{totals.get('on_num', 0)}/{totals.get('on_den', 0)}", styles['cell_bold_center']),
        Paragraph(_rate_or_dash(totals.get('on_den', 0), totals.get('on_rate', 0)), styles['cell_bold_center']),
        Paragraph(f"{totals.get('skill_pass', 0)}/{totals.get('skill_total', 0)}", styles['cell_bold_center']),
        Paragraph(_rate_or_dash(totals.get('skill_total', 0), totals.get('skill_rate', 0)), styles['cell_bold_center']),
    ])

    story.append(styled_table(
        rows_data, col_widths=[9 * mm, None, 22 * mm, 24 * mm, 15 * mm, 24 * mm, 15 * mm],
        extra_style=[
            ('SPAN', (0, total_row_idx), (2, total_row_idx)),
            ('ALIGN', (0, total_row_idx), (2, total_row_idx), 'RIGHT'),
        ],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        f"Đã loại khỏi diện đánh giá trong kỳ: {totals.get('excl_resigned', 0)} nhân sự nghỉ việc · "
        f"{totals.get('excl_next_period', 0)} nhân sự đánh giá kỳ sau (vào cuối tháng). Nhà hàng chỉ có "
        f"nhân sự bị loại vẫn được liệt kê (0/0) kèm ghi chú.",
        styles['muted'],
    ))
    story.append(Paragraph(
        'Ghi chú: "Đúng lộ trình" = hoàn thành thử việc trong hạn theo cấp (S:15 ngày · Giám sát/Bếp '
        'phó:30 · QLNH/Bếp trưởng:60). Chỉ tính Khối Nhà hàng, cấp S (fulltime) và cấp O (quản lý); đã '
        'LOẠI Khối Văn phòng, part-time (cấp P), nhân sự nghỉ việc và nhân sự có hạn đánh giá rơi sang '
        'kỳ sau. Mục tiêu ≥ 90% (lộ trình) · ≥ 85% (kỹ năng lần đầu).',
        styles['muted'],
    ))

    am_kcs = ctx.get('am_kcs') or []
    if am_kcs:
        story.append(Spacer(1, 10))
        story.append(Paragraph(
            '<b>Thống kê theo AM / KCS</b> '
            '<font color="#666666" size=9>(tiêu chí như BQL, gộp toàn bộ nhân sự trong phạm vi quản lý)</font>',
            styles['body'],
        ))
        story.append(Spacer(1, 4))
        am_rows = [[
            Paragraph('Vị trí', styles['cell_bold_center']), Paragraph('Người phụ trách', styles['cell_bold']),
            Paragraph('Phạm vi', styles['cell_bold']), Paragraph('Số NV trong kỳ', styles['cell_bold_center']),
            Paragraph('NV đúng lộ trình', styles['cell_bold_center']),
            Paragraph('Đạt kỹ năng lần đầu', styles['cell_bold_center']),
        ]]
        for item in am_kcs:
            am_rows.append([
                Paragraph(item.get('role', ''), styles['cell_center']),
                Paragraph(item.get('name', ''), styles['cell']),
                Paragraph(item.get('scope', ''), styles['cell']),
                Paragraph(str(item.get('emp_count', 0)), styles['cell_center']),
                Paragraph(_rate_or_dash(item.get('on_den', 0), item.get('on_rate', 0)), styles['cell_center']),
                Paragraph(_rate_or_dash(item.get('skill_total', 0), item.get('skill_rate', 0)), styles['cell_center']),
            ])
        story.append(styled_table(am_rows, col_widths=[14 * mm, None, 40 * mm, 24 * mm, 24 * mm, 24 * mm]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            'AM/OM: gộp toàn hệ thống (cả bếp BOH và bàn FOH). KCS: chỉ nhân sự bếp (BOH), gộp các nhà '
            'hàng phụ trách. Số liệu tính theo nhân sự (tổng đạt / tổng diện).',
            styles['muted'],
        ))

    sign_block = [
        Spacer(1, 12),
        styled_table(
            [
                [Paragraph('Người lập (Phòng Đào tạo)', styles['cell_bold_center'])],
                [Spacer(1, 25 * mm)],
                [Paragraph('(Ký, ghi rõ họ tên)', styles['caption'])],
            ],
            col_widths=[None], header=False,
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


# Khoi ky Phieu phu cap Trainer (Apps Script 05-07/08/2026): thu tu BGD -> Dao tao -> HCNS ->
# Van hanh, moi cot ten phong ban + "(Ky, ghi ro ho ten)" in nghieng xam NGAY duoi ten phong
# ban + ten nguoi ky da co san.
ALLOWANCE_SIGNERS = [
    ('Ban Giám đốc', 'Nguyễn Ngọc Diệp', 'Giám đốc'),
    ('Phòng Đào tạo', 'Nguyễn Văn Tam', 'Phó phòng Đào tạo'),
    ('Phòng HCNS', 'Nguyễn Thị Mỹ Xuân', 'Trưởng phòng HCNS'),
    ('Phòng Vận hành', 'Lưu Đức Hiệp', 'Trưởng phòng Vận hành'),
]


def build_allowance_pdf(ctx):
    """ctx keys: record_no, tenant_name, month, year, generated, rows:[{trainer,trainer_code,
    trainer_restaurant,employee,status,amount}], total_amount. Phieu phu cap trainer - giao
    dien cap nhat theo Apps Script 05-07/08/2026 (Phan 3 muc 3.2)."""
    styles = pdf_styles()
    story = []
    month, year = ctx['month'], ctx['year']

    story.append(pdf_header_block(
        'PHIẾU TỔNG HỢP PHỤ CẤP ĐÀO TẠO (TRAINER)',
        f"{ctx.get('tenant_name', '')} · Kỳ: Tháng {month}/{year}",
        [f"Ngày lập: {ctx.get('generated', '')}"], styles,
    ))
    story.append(Spacer(1, 10))

    rows_data = [[
        Paragraph('STT', styles['cell_bold_center']), Paragraph('Trainer', styles['cell_bold']),
        Paragraph('Mã NV trainer', styles['cell_bold_center']), Paragraph('Nhà hàng trainer', styles['cell_bold']),
        Paragraph('Nhân sự', styles['cell_bold']), Paragraph('Trạng thái', styles['cell_bold_center']),
        Paragraph('Phụ cấp', styles['cell_bold_center']),
    ]]
    for idx, row in enumerate(ctx.get('rows', []), start=1):
        rows_data.append([
            Paragraph(str(idx), styles['cell_center']),
            Paragraph(row.get('trainer', ''), styles['cell']),
            Paragraph(row.get('trainer_code', ''), styles['cell_center']),
            Paragraph(row.get('trainer_restaurant', ''), styles['cell']),
            Paragraph(row.get('employee', ''), styles['cell']),
            Paragraph(row.get('status', ''), styles['cell_center']),
            Paragraph(_format_vnd(row.get('amount', 0)), ParagraphStyle(
                'amount_right', parent=styles['cell'], alignment=2,
            )),
        ])

    total_row_idx = len(rows_data)
    rows_data.append([
        Paragraph('TỔNG CỘNG', styles['cell_bold_center']), '', '', '', '', '',
        Paragraph(_format_vnd(ctx.get('total_amount', 0)), ParagraphStyle(
            'total_amount_right', parent=styles['cell_bold'], alignment=2,
        )),
    ])

    story.append(styled_table(
        rows_data, col_widths=[8 * mm, 30 * mm, 24 * mm, 30 * mm, None, 22 * mm, 26 * mm],
        extra_style=[
            ('SPAN', (0, total_row_idx), (5, total_row_idx)),
            ('ALIGN', (0, total_row_idx), (5, total_row_idx), 'RIGHT'),
        ],
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'Phụ cấp 300.000đ/nhân sự khi đủ 5 điều kiện (LMS + thi ≥80% + đào tạo 100% + đánh giá kỹ năng '
        '≥85% + làm đủ 1 tháng). Phiếu nộp bộ phận C&amp;B tính lương.',
        styles['muted'],
    ))

    sign_header_style = ParagraphStyle(
        'sign_dept_header', fontName='VNSans-Bold', fontSize=10, textColor=colors.HexColor('#222222'),
        leading=13, alignment=1,
    )
    sign_name_style = ParagraphStyle(
        'sign_name', fontName='VNSans-Bold', fontSize=10, textColor=colors.HexColor('#222222'),
        leading=13, alignment=1,
    )
    header_row = [
        Paragraph(f"{dept}<br/><i><font color='#666666' size=8>(Ký, ghi rõ họ tên)</font></i>", sign_header_style)
        for dept, _name, _title in ALLOWANCE_SIGNERS
    ]
    name_row = [
        Paragraph(f"{name}<br/><font color='#666666' size=9>{title}</font>", sign_name_style)
        for _dept, name, title in ALLOWANCE_SIGNERS
    ]
    sign_block = [
        Spacer(1, 12),
        styled_table(
            [header_row, [Spacer(1, 22 * mm) for _ in ALLOWANCE_SIGNERS], name_row],
            col_widths=[None] * len(ALLOWANCE_SIGNERS), header=False,
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
