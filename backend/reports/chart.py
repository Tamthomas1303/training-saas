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

# Bo cuc bieu do: moi cot rong 56-90px (tuy so luong nha hang), tong vung ve toi thieu
# MIN_CHART_WIDTH de khong bi hep khi it nha hang. height/margin_bottom tang de chua du nhan
# ten nha hang xoay nghieng khong bi cat/chong nhau.
MIN_CHART_WIDTH = 560
BAR_SLOT_MIN, BAR_SLOT_MAX = 56, 90
CHART_HEIGHT = 420
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 50, 24, 40, 96


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

    n = len(restaurants)
    margin_left, margin_right, margin_top, margin_bottom = MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM
    bar_slot = max(BAR_SLOT_MIN, min(BAR_SLOT_MAX, MIN_CHART_WIDTH // n))
    chart_w = max(MIN_CHART_WIDTH, bar_slot * n)
    width = margin_left + chart_w + margin_right
    height = CHART_HEIGHT
    chart_h = height - margin_top - margin_bottom

    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    draw.text((margin_left, 8), title, fill=(30, 30, 30), font=font)

    for i in range(0, 101, 20):
        y = margin_top + chart_h - (i / 100 * chart_h)
        draw.line([(margin_left, y), (width - margin_right, y)], fill=(228, 228, 228))
        draw.text((6, y - 6), str(i), fill=(120, 120, 120), font=font_small)

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
