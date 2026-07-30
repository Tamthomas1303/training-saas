"""Ve bieu do cot diem cham dich vu theo nha hang, tra ve PNG bytes.

Dung Pillow (da co san trong requirements.txt, da xac nhan chay duoc) thay vi
reportlab.graphics.renderPM - da thu va xac nhan renderPM can them goi rlPyCairo (-> Cairo
native) khong co san trong moi truong nay, giong y het truong hop WeasyPrint da gap trong
sprint thiet ke lai PDF. Pillow la thu vien C-extension co san wheel, khong can them thu vien
he thong nao.
"""
import io

from PIL import Image, ImageDraw, ImageFont

BAR_COLOR_OK = (30, 111, 92)      # #1e6f5c - trung voi mau chu dao cua he thong
BAR_COLOR_LOW = (192, 57, 43)     # #c0392b - diem thap (< SCORE_WARN_THRESHOLD)
SCORE_WARN_THRESHOLD = 70


def _load_font(size):
    from django.conf import settings

    font_path = settings.BASE_DIR / 'checklist' / 'fonts' / 'DejaVuSans.ttf'
    try:
        return ImageFont.truetype(str(font_path), size)
    except OSError:
        return ImageFont.load_default()


def render_service_score_chart(restaurants, title='Điểm chấm dịch vụ theo nhà hàng (%)'):
    """restaurants: [{'restaurant': str, 'score': float|None}, ...]. Tra ve PNG bytes, None
    neu rong."""
    if not restaurants:
        return None

    font = _load_font(13)
    font_small = _load_font(11)

    margin_left, margin_right, margin_top, margin_bottom = 46, 20, 34, 80
    bar_area_w = max(90, min(70, 640 // max(1, len(restaurants)))) * len(restaurants)
    width = margin_left + bar_area_w + margin_right
    height = 340
    chart_h = height - margin_top - margin_bottom
    chart_w = width - margin_left - margin_right

    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    draw.text((margin_left, 8), title, fill=(30, 30, 30), font=font)

    for i in range(0, 101, 20):
        y = margin_top + chart_h - (i / 100 * chart_h)
        draw.line([(margin_left, y), (width - margin_right, y)], fill=(228, 228, 228))
        draw.text((6, y - 6), str(i), fill=(120, 120, 120), font=font_small)

    n = len(restaurants)
    bar_w = chart_w / n
    base_y = margin_top + chart_h
    for i, r in enumerate(restaurants):
        score = r['score'] or 0
        bar_h = min(score, 100) / 100 * chart_h
        x0 = margin_left + i * bar_w + bar_w * 0.18
        x1 = margin_left + (i + 1) * bar_w - bar_w * 0.18
        y0 = base_y - bar_h
        color = BAR_COLOR_OK if score >= SCORE_WARN_THRESHOLD else BAR_COLOR_LOW
        draw.rectangle([x0, y0, x1, base_y], fill=color)
        score_label = f'{score:.0f}'
        tw = draw.textlength(score_label, font=font_small)
        draw.text((x0 + (x1 - x0 - tw) / 2, max(0, y0 - 16)), score_label, fill=(30, 30, 30), font=font_small)

        name = r['restaurant']
        label = name if len(name) <= 14 else name[:13] + '…'
        label_img = Image.new('RGBA', (140, 18), (255, 255, 255, 0))
        ImageDraw.Draw(label_img).text((0, 0), label, fill=(40, 40, 40), font=font_small)
        rotated = label_img.rotate(35, expand=True, resample=Image.BICUBIC)
        img.paste(rotated, (int(x0 - 10), int(base_y + 6)), rotated)

    draw.line([(margin_left, margin_top), (margin_left, base_y)], fill=(90, 90, 90))
    draw.line([(margin_left, base_y), (width - margin_right, base_y)], fill=(90, 90, 90))

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()
