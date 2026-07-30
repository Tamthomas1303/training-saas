"""Xuat phieu ket qua thu viec (PDF). Port ResultService.gs::generateProbationResultPdf +
phan hoi "Phan 1" (them cot chu ky Trainer/anh cho checklist, cot anh + 2 chu ky + ngay +
ten nguoi danh gia cho danh gia thuc hanh).

build_probation_result_pdf dung Platypus (xem checklist/pdf.py) - bang co vien/header
nen/padding, KeepTogether cho cac khoi chu ky. build_levelup_proposal_pdf van dung canvas
truc tiep (chua thiet ke lai dot nay).

Dung lai font/helper da dang ky o checklist.pdf (VNSans) de khong dang ky font 2 lan.
"""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

from checklist.pdf import (
    PAGE_MARGIN, _fetch_image, _placeholder_box, ensure_space, pdf_header_block, pdf_styles,
    platypus_image, styled_table,
)


def build_levelup_proposal_pdf(ctx):
    """Phiếu ĐỀ XUẤT LÊN LEVEL (#9). ctx: tenant_name, date, employee{name,code,position,
    restaurant,start_date}, from_level, target_level, target_position, achieved_positions:[..],
    positions_count, completion{lms, exam_pass, exam_score, checklist_percent, skill_percent,
    combined_score, threshold}."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 18 * mm
    y = height - margin

    def line(text, size=11, dy=16, bold=False, x=None):
        nonlocal y
        c.setFont('VNSans-Bold' if bold else 'VNSans', size)
        c.drawString(x if x is not None else margin, y, text)
        y -= dy

    c.setFont('VNSans-Bold', 15)
    c.drawCentredString(width / 2, y, 'PHIẾU ĐỀ XUẤT NÂNG LEVEL')
    y -= 18
    c.setFont('VNSans', 9)
    c.drawCentredString(width / 2, y, ctx.get('tenant_name', ''))
    y -= 8
    c.setFont('VNSans', 9)
    c.drawCentredString(width / 2, y, f"Ngày lập: {ctx.get('date', '')}")
    y -= 20

    e = ctx.get('employee', {})
    line(f"Nhân sự: {e.get('name', '')}  -  Mã: {e.get('code', '')}", bold=True)
    line(f"Vị trí hiện tại: {e.get('position', '')}   ·   Nhà hàng: {e.get('restaurant', '')}")
    line(f"Ngày vào làm: {e.get('start_date', '')}")
    y -= 4
    line(f"ĐỀ XUẤT: nâng level {ctx.get('from_level', '')}  →  {ctx.get('target_level', '')}", bold=True, size=12)
    line(f"Hoàn thành vị trí: {ctx.get('target_position', '')}   ·   Tổng vị trí đã đạt: {ctx.get('positions_count', '')}")
    ap = ctx.get('achieved_positions') or []
    if ap:
        line("Các vị trí đã đạt: " + ', '.join(ap), size=10)
    y -= 6

    comp = ctx.get('completion', {})
    line("Căn cứ hoàn thành:", bold=True)
    line(f"  • LMS học lý thuyết: {'Đạt' if comp.get('lms') else 'Chưa'}", size=10, dy=14)
    line(f"  • Thi lý thuyết: {'Đạt' if comp.get('exam_pass') else 'Chưa'} (điểm {comp.get('exam_score', 0)})", size=10, dy=14)
    line(f"  • Đào tạo tại điểm (checklist): {comp.get('checklist_percent', 0)}%", size=10, dy=14)
    line(f"  • Đánh giá thực hành: {comp.get('skill_percent', 0)}%", size=10, dy=14)
    line(f"  • Điểm tổng (40% thi + 60% thực hành): {comp.get('combined_score', 0)}% "
         f"(chuẩn ≥ {comp.get('threshold', 85)}%)", size=10, dy=16, bold=True)
    y -= 10

    line("Đề xuất Phòng Đào tạo trình cấp thẩm quyền phê duyệt nâng level & điều chỉnh bậc lương "
         "theo quy chế (mỗi lần tăng 1 level).", size=10)
    y -= 30

    # 3 o chu ky - giu nguyen ven ca 3 nhan + dong "(Ky, ghi ro ho ten)" tren cung 1 trang.
    y = ensure_space(c, y, height, margin, 42 + 14)
    col_w = (width - 2 * margin) / 3
    labels = ['Người lập (Phòng Đào tạo)', 'Quản lý nhà hàng', 'Phê duyệt (BGĐ/HCNS)']
    c.setFont('VNSans', 10)
    for i, lb in enumerate(labels):
        cx = margin + col_w * i + col_w / 2
        c.drawCentredString(cx, y, lb)
    y -= 42
    c.setFont('VNSans', 9)
    for i in range(3):
        cx = margin + col_w * i + col_w / 2
        c.drawCentredString(cx, y, '(Ký, ghi rõ họ tên)')

    c.showPage()
    c.save()
    return buf.getvalue()


def build_probation_result_pdf(ctx):
    """ctx keys: record_no, tenant_name, date, employee_code, employee{name,position,
    restaurant,start_date}, checklist:[{name,date,sign_trainer_url,sign_trainee_url,
    photos:[url,url,url]}], skill_eval: {date,evaluator_name,sign_evaluator_url,
    sign_trainee_url,items:[{content,max_score,score,photo_url}]} hoac None,
    courses[{name,score,status}], exams[{name,score,passed,is_regrade}], score_exam,
    score_practice, score_final, final_status, pass_date (dd/MM/YYYY, chi dung khi
    final_status = 'Pass thử việc'), signer_name, signer_title.
    Diem thi (score_exam) la diem CAO NHAT (xem employees/services.py::best_exam_score) -
    'is_regrade' tren tung dong exam la cho de danh dau lan phuc khao (Task 2, chua co model
    that su) bang nhan "(PK)", khong anh huong cach tinh score_exam tong hop.
    Dung Platypus - bang co vien/header nen, KeepTogether cho 2 khoi chu ky."""
    styles = pdf_styles()
    story = []
    emp = ctx.get('employee', {})

    story.append(pdf_header_block(
        'PHIẾU KẾT QUẢ THỬ VIỆC', ctx.get('tenant_name', ''),
        [f"Số: {ctx['record_no']}", f"Ngày: {ctx.get('date', '')}"], styles,
    ))
    story.append(Spacer(1, 10))

    story.append(styled_table(
        [
            [Paragraph('Họ tên', styles['cell_bold']),
             Paragraph(f"{emp.get('name', '')} - {ctx.get('employee_code', '')}", styles['cell']),
             Paragraph('Vị trí', styles['cell_bold']), Paragraph(emp.get('position', ''), styles['cell'])],
            [Paragraph('Nhà hàng', styles['cell_bold']), Paragraph(emp.get('restaurant', ''), styles['cell']),
             Paragraph('Ngày vào làm', styles['cell_bold']), Paragraph(emp.get('start_date', ''), styles['cell'])],
        ],
        col_widths=[28 * mm, 62 * mm, 28 * mm, 56 * mm], header=False,
    ))

    # 1. Ket qua hoc & thi (LMS)
    story.append(Paragraph('1. Kết quả học &amp; thi (LMS)', styles['h3']))
    courses = ctx.get('courses') or []
    if courses:
        rows = [[Paragraph('Tên khóa học', styles['cell_bold']), Paragraph('Điểm', styles['cell_bold']),
                  Paragraph('Kết quả', styles['cell_bold'])]]
        for course in courses:
            rows.append([
                Paragraph(course.get('name', ''), styles['cell']),
                Paragraph(str(course.get('score', '')), styles['cell_center']),
                Paragraph(course.get('status', ''), styles['cell_center']),
            ])
        story.append(styled_table(rows, col_widths=[None, 28 * mm, 28 * mm]))
        story.append(Spacer(1, 6))

    exams = ctx.get('exams') or []
    if exams:
        rows = [[Paragraph('Tên bài thi', styles['cell_bold']), Paragraph('Điểm', styles['cell_bold']),
                  Paragraph('Kết quả', styles['cell_bold'])]]
        for exam in exams:
            score_text = str(exam.get('score', ''))
            if exam.get('is_regrade'):
                score_text += ' (PK)'
            rows.append([
                Paragraph(exam.get('name', ''), styles['cell']),
                Paragraph(score_text, styles['cell_center']),
                Paragraph('Đạt' if exam.get('passed') else 'Không đạt', styles['cell_center']),
            ])
        story.append(styled_table(rows, col_widths=[None, 28 * mm, 28 * mm]))

    # 2. Checklist dao tao (co xac nhan cua hoc vien)
    checklist = ctx.get('checklist') or []
    if checklist:
        story.append(Paragraph('2. Checklist đào tạo (có xác nhận của học viên)', styles['h3']))
        rows = [[
            Paragraph('STT', styles['cell_bold']), Paragraph('Nội dung', styles['cell_bold']),
            Paragraph('Ngày ĐT', styles['cell_bold']), Paragraph('Ảnh minh chứng', styles['cell_bold']),
            Paragraph('Ký Trainer', styles['cell_bold']), Paragraph('Ký HV', styles['cell_bold']),
        ]]
        for idx, item in enumerate(checklist, start=1):
            photo_url = next((u for u in (item.get('photos') or []) if u), None)
            rows.append([
                Paragraph(str(idx), styles['cell_center']),
                Paragraph(item.get('name', ''), styles['cell']),
                Paragraph(item.get('date', ''), styles['cell_center']),
                platypus_image(photo_url, 26 * mm, 20 * mm),
                platypus_image(item.get('sign_trainer_url'), 30 * mm, 20 * mm),
                platypus_image(item.get('sign_trainee_url'), 30 * mm, 20 * mm),
            ])
        story.append(styled_table(
            rows, col_widths=[10 * mm, None, 20 * mm, 30 * mm, 32 * mm, 32 * mm],
        ))
        story.append(Spacer(1, 6))

    # 3. Danh gia thuc hanh (ky nang)
    skill_eval = ctx.get('skill_eval')
    if skill_eval:
        story.append(Paragraph('3. Đánh giá thực hành', styles['h3']))
        rows = [[
            Paragraph('STT', styles['cell_bold']), Paragraph('Tiêu chí', styles['cell_bold']),
            Paragraph('Tối đa', styles['cell_bold']), Paragraph('Điểm', styles['cell_bold']),
            Paragraph('Ảnh', styles['cell_bold']),
        ]]
        for idx, item in enumerate(skill_eval.get('items', []), start=1):
            rows.append([
                Paragraph(str(idx), styles['cell_center']),
                Paragraph(item.get('content', ''), styles['cell']),
                Paragraph(str(item.get('max_score', '')), styles['cell_center']),
                Paragraph(str(item.get('score', '')), styles['cell_center']),
                platypus_image(item.get('photo_url'), 26 * mm, 20 * mm),
            ])
        story.append(styled_table(rows, col_widths=[10 * mm, None, 20 * mm, 20 * mm, 30 * mm]))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"Ngày đánh giá: {skill_eval.get('date', '')} &nbsp;&nbsp; "
            f"Người đánh giá: {skill_eval.get('evaluator_name', '')}",
            styles['muted'],
        ))

        sign_w, sign_h = 200, 90
        sign_block = [
            Spacer(1, 6),
            styled_table(
                [
                    [Paragraph('Người đánh giá', styles['cell_bold']), Paragraph('Học viên', styles['cell_bold'])],
                    [
                        platypus_image(skill_eval.get('sign_evaluator_url'), sign_w, sign_h),
                        platypus_image(skill_eval.get('sign_trainee_url'), sign_w, sign_h),
                    ],
                    [
                        Paragraph(skill_eval.get('evaluator_name', ''), styles['caption']),
                        Paragraph(emp.get('name', ''), styles['caption']),
                    ],
                ],
                col_widths=[None, None], header=False,
            ),
        ]
        story.append(KeepTogether(sign_block))

    # 4. Tong hop
    story.append(Paragraph('4. Tổng hợp', styles['h3']))
    story.append(styled_table(
        [
            [Paragraph('Điểm thi', styles['cell_bold_center']), Paragraph('Điểm thực hành', styles['cell_bold_center']),
             Paragraph('Điểm tổng hợp', styles['cell_bold_center'])],
            [
                Paragraph(str(ctx.get('score_exam', '')), styles['cell_center']),
                Paragraph(str(ctx.get('score_practice', '')), styles['cell_center']),
                Paragraph(str(ctx.get('score_final', '')), styles['cell_center']),
            ],
        ],
        col_widths=[None, None, None],
    ))
    story.append(Spacer(1, 6))
    final_status = ctx.get('final_status', '')
    if final_status == 'Pass thử việc' and ctx.get('pass_date'):
        status_text = f"Trạng thái: Pass thử việc ngày {ctx['pass_date']}"
    else:
        status_text = f"Trạng thái: {final_status}"
    story.append(Paragraph(
        f"<b><font color='#1e6f5c'>{status_text}</font></b>", styles['body'],
    ))

    signer_name_style = ParagraphStyle('signer_name_center', parent=styles['body_bold'], alignment=1)
    signer_title_style = ParagraphStyle('signer_title_center', parent=styles['muted'], alignment=1)
    signer_heading_style = ParagraphStyle('signer_heading_center', parent=styles['h3'], alignment=1)

    signer_block = [
        Spacer(1, 10),
        Paragraph('Xác nhận từ Phòng Đào tạo', signer_heading_style),
        Spacer(1, 25 * mm),  # khoang trong de ky tuoi (khong ve o vien nhu truoc)
        Paragraph(ctx.get('signer_name', ''), signer_name_style),
        Paragraph(ctx.get('signer_title', ''), signer_title_style),
    ]
    story.append(KeepTogether(signer_block))

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=PAGE_MARGIN, rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN, bottomMargin=PAGE_MARGIN,
    )
    doc.build(story)
    return buf.getvalue()
