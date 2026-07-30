"""
Sinh phieu danh gia ky nang (PDF) cho 1 Evaluation da hoan thanh.

Port bo cuc tu PDFService.gs::buildEvaluation (AppsScript Ver 2.0): header + thong tin
nhan su + bang tieu chi (noi dung/diem toi da/diem dat/anh) + dong tong+ket qua + ghi chu +
2 chu ky (nguoi danh gia/nhan vien). Dung Platypus (SimpleDocTemplate + Table/Paragraph,
xem checklist/pdf.py) - bang co vien/header nen/padding chuan, KeepTogether cho khoi chu ky.
"""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from checklist.pdf import PAGE_MARGIN, pdf_header_block, pdf_styles, platypus_image, styled_table


def build_evaluation_pdf(ctx):
    """ctx keys: record_no, tenant_name, eval_type_label, employee{name,position,restaurant,start_date},
    evaluator_name, rows:[{content,max_score,score,photo_url}], total, max, percent, result, note,
    sign_evaluator_url, sign_trainee_url.
    Tra ve PDF bytes.
    """
    styles = pdf_styles()
    story = []
    emp = ctx.get('employee', {})

    story.append(pdf_header_block(
        'PHIẾU ĐÁNH GIÁ KỸ NĂNG', f"{ctx.get('tenant_name', '')} · {ctx.get('eval_type_label', '')}",
        [f"Số: {ctx['record_no']}", f"Ngày: {ctx.get('date', '')}"], styles,
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

    story.append(Paragraph('TIÊU CHÍ ĐÁNH GIÁ', styles['h3']))
    header_row = [
        Paragraph('Nội dung', styles['cell_bold']), Paragraph('Điểm tối đa', styles['cell_bold']),
        Paragraph('Điểm đạt', styles['cell_bold']), Paragraph('Ảnh', styles['cell_bold']),
    ]
    body_rows = []
    for idx, row in enumerate(ctx['rows'], start=1):
        body_rows.append([
            Paragraph(f"{idx}. {row.get('content', '')}", styles['cell']),
            Paragraph(str(row.get('max_score', '')), styles['cell_center']),
            Paragraph(str(row.get('score', '')), styles['cell_center']),
            platypus_image(row.get('photo_url'), 50, 40),
        ])
    story.append(styled_table([header_row] + body_rows, col_widths=[None, 22 * mm, 22 * mm, 22 * mm]))

    result_text = ctx.get('result', '')
    result_style = styles['result_pass'] if result_text == 'Đạt' else styles['result_fail']
    story.append(styled_table(
        [[
            Paragraph('Tổng / Kết quả', styles['cell_bold']),
            Paragraph(str(ctx.get('max', '')), styles['cell_center']),
            Paragraph(f"{ctx.get('total', '')} ({ctx.get('percent', 0)}%)", styles['cell_center']),
            Paragraph(result_text, result_style),
        ]],
        col_widths=[None, 22 * mm, 22 * mm, 22 * mm], header=False,
    ))

    if ctx.get('note'):
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"Ghi chú: {ctx['note']}", styles['body']))

    sign_w, sign_h = 200, 90
    sign_block = [
        Paragraph('XÁC NHẬN', styles['h3']),
        styled_table(
            [
                [Paragraph('Người đánh giá', styles['cell_bold']), Paragraph('Nhân viên', styles['cell_bold'])],
                [
                    platypus_image(ctx.get('sign_evaluator_url'), sign_w, sign_h),
                    platypus_image(ctx.get('sign_trainee_url'), sign_w, sign_h),
                ],
                [
                    Paragraph(ctx.get('evaluator_name', ''), styles['caption']),
                    Paragraph(emp.get('name', ''), styles['caption']),
                ],
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
