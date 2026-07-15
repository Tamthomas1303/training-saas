"""Xuat phieu ket qua thu viec (PDF). Port ResultService.gs::generateProbationResultPdf +
phan hoi "Phan 1" (them cot chu ky Trainer/anh cho checklist, cot anh + 2 chu ky + ngay +
ten nguoi danh gia cho danh gia thuc hanh).

Dung lai font/helper da dang ky o checklist.pdf (VNSans) de khong dang ky font 2 lan.
"""
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from checklist.pdf import _fetch_image, _placeholder_box


def build_probation_result_pdf(ctx):
    """ctx keys: record_no, tenant_name, employee_code, employee{name,position,restaurant,
    start_date}, checklist:[{name,date,sign_trainer_url,photos:[url,url,url]}],
    skill_eval: {date,evaluator_name,sign_evaluator_url,sign_trainee_url,
    items:[{content,max_score,score,photo_url}]} hoac None, courses[{name,status}],
    exams[{name,score}], score_exam, score_practice, score_final, final_status,
    signer_name, signer_title."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    margin = 15 * mm
    y = height - margin

    def line(text, size=11, dy=16, bold=False):
        nonlocal y
        c.setFont('VNSans-Bold' if bold else 'VNSans', size)
        c.drawString(margin, y, text)
        y -= dy

    def ensure_space(needed):
        nonlocal y
        if y - needed < 20 * mm:
            c.showPage()
            y = height - margin

    c.setFont('VNSans-Bold', 15)
    c.drawCentredString(width / 2, y, 'PHIẾU KẾT QUẢ THỬ VIỆC')
    y -= 20
    c.setFont('VNSans', 9)
    c.drawCentredString(width / 2, y, ctx.get('tenant_name', ''))
    y -= 22

    line(f"Số phiếu: {ctx['record_no']}", size=10)
    y -= 4

    line('THÔNG TIN NHÂN SỰ', bold=True, size=12)
    line(f"Họ tên: {ctx['employee'].get('name', '')} - {ctx.get('employee_code', '')}")
    line(f"Vị trí: {ctx['employee'].get('position', '')}")
    line(f"Nhà hàng: {ctx['employee'].get('restaurant', '')}")
    line(f"Ngày vào làm: {ctx['employee'].get('start_date', '')}")
    y -= 4

    # Checklist dao tao (co xac nhan cua hoc vien): dau viec | ngay | chu ky Trainer | anh
    checklist = ctx.get('checklist') or []
    if checklist:
        ensure_space(30)
        line('CHECKLIST ĐÀO TẠO (CÓ XÁC NHẬN CỦA HỌC VIÊN)', bold=True, size=12)
        row_h = 32
        c.setFont('VNSans-Bold', 8)
        c.drawString(margin, y, 'Đầu việc')
        c.drawString(margin + 190, y, 'Ngày')
        c.drawString(margin + 240, y, 'Ký Trainer')
        c.drawString(margin + 310, y, 'Ảnh minh chứng')
        y -= 12
        for item in checklist:
            ensure_space(row_h + 4)
            c.setFont('VNSans', 8)
            c.drawString(margin, y, (item.get('name') or '')[:38])
            c.drawString(margin + 190, y, item.get('date') or '')
            sign_x = margin + 240
            img = _fetch_image(item.get('sign_trainer_url'))
            if img:
                c.drawImage(img, sign_x, y - 22, width=55, height=24, preserveAspectRatio=True, anchor='c')
            else:
                _placeholder_box(c, sign_x, y + 2, 55, 24)
            px = margin + 310
            for photo_url in (item.get('photos') or [])[:3]:
                pimg = _fetch_image(photo_url)
                if pimg:
                    c.drawImage(pimg, px, y - 22, width=26, height=24, preserveAspectRatio=True, anchor='c')
                else:
                    _placeholder_box(c, px, y + 2, 26, 24)
                px += 29
            y -= row_h
        y -= 6

    # Danh gia thuc hanh (ky nang): tieu chi | diem | anh, roi ngay + nguoi danh gia + 2 chu ky
    skill_eval = ctx.get('skill_eval')
    if skill_eval:
        ensure_space(40)
        line('ĐÁNH GIÁ THỰC HÀNH (KỸ NĂNG)', bold=True, size=12)
        row_h = 28
        c.setFont('VNSans-Bold', 8)
        c.drawString(margin, y, 'Tiêu chí')
        c.drawString(margin + 260, y, 'Điểm')
        c.drawString(margin + 320, y, 'Ảnh minh chứng')
        y -= 12
        for item in skill_eval.get('items', []):
            ensure_space(row_h + 4)
            c.setFont('VNSans', 8)
            c.drawString(margin, y, (item.get('content') or '')[:44])
            c.drawString(margin + 260, y, f"{item.get('score', 0)}/{item.get('max_score', 0)}")
            px = margin + 320
            pimg = _fetch_image(item.get('photo_url'))
            if pimg:
                c.drawImage(pimg, px, y - 20, width=40, height=22, preserveAspectRatio=True, anchor='c')
            else:
                _placeholder_box(c, px, y + 2, 40, 22)
            y -= row_h
        y -= 4
        ensure_space(16)
        line(
            f"Ngày đánh giá: {skill_eval.get('date', '')}    "
            f"Người đánh giá: {skill_eval.get('evaluator_name', '')}",
            size=9,
        )
        y -= 6
        ensure_space(45)
        sign_w, sign_h = 55 * mm, 22 * mm
        for i, (label, url) in enumerate([
            ('Người đánh giá', skill_eval.get('sign_evaluator_url')),
            ('Học viên', skill_eval.get('sign_trainee_url')),
        ]):
            x = margin + i * (sign_w + 10 * mm)
            img = _fetch_image(url)
            if img:
                c.drawImage(img, x, y - sign_h, width=sign_w, height=sign_h, preserveAspectRatio=True, anchor='c')
            else:
                _placeholder_box(c, x, y, sign_w, sign_h)
            c.setFont('VNSans', 9)
            c.drawCentredString(x + sign_w / 2, y - sign_h - 10, label)
        y -= sign_h + 24

    ensure_space(70)
    line('KẾT QUẢ HỌC & THI LMS', bold=True, size=12)
    for course in ctx.get('courses', []):
        ensure_space(16)
        line(f"- {course.get('name', '')}: {course.get('status', '')}", size=10)
    for exam in ctx.get('exams', []):
        ensure_space(16)
        line(f"- {exam.get('name', '')}: {exam.get('score', '')} điểm", size=10)
    y -= 4

    ensure_space(90)
    line('ĐIỂM TỔNG HỢP', bold=True, size=12)
    line(f"Điểm thi lý thuyết: {ctx.get('score_exam', '')}")
    line(f"Điểm thực hành/kỹ năng: {ctx.get('score_practice', '')}")
    line(f"Điểm tổng kết (40% thi + 60% thực hành): {ctx.get('score_final', '')}", bold=True)
    y -= 4
    c.setFillColorRGB(0.18, 0.44, 0.25)
    line(f"Kết quả: {ctx.get('final_status', '')}", bold=True, size=13)
    c.setFillColorRGB(0, 0, 0)
    y -= 16

    ensure_space(45)
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
