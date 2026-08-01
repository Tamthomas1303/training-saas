"""Loi phan tich GPT CHI cho khoi 4 (cham dich vu nha hang) - GPT KHONG duoc dua ra bat ky
con so nao, chi duoc viet nhan xet tu cac so lieu da tinh san bang code (xem metrics_csv.py).
Khong cai them SDK 'openai' - goi thang REST API bang requests (da co san trong requirements)
de tranh them dependency khong can thiet. Khong co OPENAI_API_KEY -> tra ve None (bo qua)."""
import logging

import requests

logger = logging.getLogger(__name__)

OPENAI_CHAT_URL = 'https://api.openai.com/v1/chat/completions'
REQUEST_TIMEOUT = 30


def build_service_audit_analysis(period_label, current, previous):
    """current/previous: ket qua service_audit_block() cua ky nay/ky truoc (co the None neu
    ky truoc chua co du lieu). Tra ve HTML <ul><li> (str, render bang |safe trong template -
    KHONG dung |linebreaksbr nua) hoac None neu khong co OPENAI_API_KEY / loi goi API (khong
    lam hong ca bao cao)."""
    from django.conf import settings

    if not settings.OPENAI_API_KEY:
        return None

    lowest_3 = sorted(
        [r for r in current['restaurants'] if r['score'] is not None], key=lambda r: r['score'],
    )[:3]
    prompt_lines = [
        f"Đây là số liệu chấm dịch vụ nhà hàng (khối Đào tạo) kỳ báo cáo: {period_label}.",
        f"Điểm trung bình toàn hệ thống kỳ này: {current['overall_score']}%.",
    ]
    if previous and previous.get('overall_score') is not None:
        prompt_lines.append(f"Điểm trung bình kỳ trước: {previous['overall_score']}%.")
    else:
        prompt_lines.append('Không có số liệu kỳ trước để so sánh.')

    prompt_lines.append('3 nhà hàng điểm thấp nhất kỳ này:')
    for r in lowest_3:
        prompt_lines.append(f"- {r['restaurant']}: {r['score']}%")

    if current['top_problems']:
        prompt_lines.append('Các tiêu chí bị điểm 0 lặp lại nhiều nhất:')
        for p in current['top_problems']:
            prompt_lines.append(f"- {p['criteria']} (xuất hiện {p['count']} lần)")

    prompt_lines.append(
        'Hãy viết nhận định cho Ban Giám đốc, chia 3 phần theo đúng thứ tự sau, mỗi phần có '
        'tiêu đề in đậm <b>...</b> rồi một <ul> gồm các <li> gạch đầu dòng NGẮN (không viết '
        'đoạn văn liền):\n'
        '<b>1. So tỷ lệ điểm</b>: so điểm trung bình kỳ này với kỳ trước (tăng/giảm bao nhiêu %).\n'
        '<b>2. So các vấn đề</b>: so các tiêu chí không đạt kỳ này với kỳ trước.\n'
        '<b>3. 3 nhà hàng thấp điểm nhất</b>: nêu 3 nhà hàng đó yếu khâu nào (dựa trên các tiêu '
        'chí không đạt đã liệt kê ở trên) và hướng khắc phục cụ thể cho từng nhà hàng.\n'
        'CHỈ dùng đúng các số liệu đã cho ở trên, KHÔNG tự bịa thêm số liệu nào khác. Chỉ trả '
        'về HTML dùng <b> và <ul><li>, không chào hỏi, không đoạn văn liền.'
    )
    prompt = '\n'.join(prompt_lines)
    return _call_openai(prompt)


def build_block_analysis(topic, period_label, current_summary, previous_summary):
    """current_summary/previous_summary: chuoi mo ta so lieu DA TINH SAN boi code (KHONG de
    GPT tu tinh) cho khoi 1 (Dao tao nhan su moi) / 2 (Kiem tra kien thuc) / 3 (To chuc dao
    tao). Tra ve HTML <ul><li> 2-4 gach dau dong ngan, hoac None neu khong co OPENAI_API_KEY /
    loi goi API (khong lam hong ca bao cao)."""
    from django.conf import settings

    if not settings.OPENAI_API_KEY:
        return None

    prompt = (
        f"Bạn là Trưởng phòng Đào tạo. CHỈ dùng số liệu cho sẵn, không bịa, mỗi ý kèm dẫn "
        f"chứng số. Viết nhận định ngắn về '{topic}', so sánh kỳ này với kỳ trước (tăng/giảm) "
        f"và nêu điểm cần cải thiện. Trả về HTML là MỘT <ul> gồm 2-4 <li> gạch đầu dòng ngắn, "
        f"không đoạn văn, không chào hỏi.\n"
        f"KỲ NÀY ({period_label}): {current_summary}\n"
        f"KỲ TRƯỚC: {previous_summary}"
    )
    return _call_openai(prompt)


def _call_openai(user_prompt):
    """Goi OpenAI Chat Completions, tra ve noi dung tra loi (str) hoac None neu loi (khong lam
    hong ca bao cao) - dung chung cho moi ham build_*_analysis trong file nay."""
    from django.conf import settings

    try:
        resp = requests.post(
            OPENAI_CHAT_URL,
            headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': settings.OPENAI_MODEL,
                'messages': [
                    {'role': 'system', 'content': 'Bạn là chuyên viên phân tích vận hành nhà hàng, viết ngắn gọn, đi thẳng vào số liệu.'},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.3,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content'].strip()
    except (requests.RequestException, KeyError, IndexError) as exc:
        logger.warning('Goi OpenAI that bai, bo qua phan phan tich: %s', exc)
        return None
