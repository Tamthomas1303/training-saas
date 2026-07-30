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
    ky truoc chua co du lieu). Tra ve doan van ban phan tich (str) hoac None neu khong co
    OPENAI_API_KEY / loi goi API (khong lam hong ca bao cao)."""
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
        'Hãy viết 1 đoạn phân tích ngắn (tối đa 120 từ) bằng tiếng Việt cho Ban Giám đốc, nêu '
        'xu hướng so với kỳ trước và gợi ý hành động cho 3 nhà hàng điểm thấp nhất. CHỈ dùng '
        'đúng các số liệu đã cho ở trên, KHÔNG tự bịa thêm số liệu nào khác.'
    )
    prompt = '\n'.join(prompt_lines)

    try:
        resp = requests.post(
            OPENAI_CHAT_URL,
            headers={'Authorization': f'Bearer {settings.OPENAI_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': settings.OPENAI_MODEL,
                'messages': [
                    {'role': 'system', 'content': 'Bạn là chuyên viên phân tích vận hành nhà hàng, viết ngắn gọn, đi thẳng vào số liệu.'},
                    {'role': 'user', 'content': prompt},
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
