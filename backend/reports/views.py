import datetime

from rest_framework.response import Response
from rest_framework.views import APIView

from .services import preview_report

REPORT_ROLES = {'admin', 'om'}


def _parse_kind_and_date(params):
    kind = params.get('kind') or 'week'
    if kind not in ('week', 'month'):
        return None, None, 'kind phải là "week" hoặc "month".'
    date_str = params.get('date')
    if date_str:
        try:
            ref_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return None, None, 'date không hợp lệ (định dạng YYYY-MM-DD).'
    else:
        ref_date = datetime.date.today()
    return kind, ref_date, None


class TrainingReportPreviewView(APIView):
    """GET /api/reports/training/preview/?kind=week|month&date=YYYY-MM-DD — render HTML bao
    cao de xem truoc tren web, chi Admin/OM."""

    def get(self, request):
        if (request.user.role or '').lower() not in REPORT_ROLES:
            return Response({'detail': 'Bạn không có quyền xem báo cáo này.'}, status=403)
        kind, ref_date, error = _parse_kind_and_date(request.query_params)
        if error:
            return Response({'detail': error}, status=400)
        result = preview_report(request.user.tenant, kind, ref_date)
        return Response(result)


class TrainingReportSendView(APIView):
    """POST /api/reports/training/send/ — DA VO HIEU HOA gui SMTP truc tiep tu web: Render
    (goi free dang dung) chan cong SMTP ra ngoai, khien socket.connect toi smtp.gmail.com:587
    treo vo han va lam worker Render bi timeout/kill. Endpoint nay CHI con tra ve huong dan,
    khong goi send_report_email nua - gui that qua GitHub Actions workflow
    "send_training_report.yml" (tu dong theo lich hoac 'Run workflow' thu cong), hoac chay
    `python manage.py send_training_report` tu may/CI co the ket noi SMTP that su.
    Giu lai route (khong xoa) de tra loi ro rang thay vi 404 cho client cu."""

    def post(self, request):
        if (request.user.role or '').lower() not in REPORT_ROLES:
            return Response({'detail': 'Bạn không có quyền gửi báo cáo này.'}, status=403)
        return Response({
            'detail': (
                'Gửi email trực tiếp từ web đã tắt vì Render (gói free) chặn cổng SMTP ra '
                'ngoài. Báo cáo được gửi tự động theo lịch (GitHub Actions) hoặc chạy tay '
                'workflow "Send Training Report" trong tab Actions của repo.'
            ),
        }, status=400)
