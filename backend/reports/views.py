import datetime

from rest_framework.response import Response
from rest_framework.views import APIView

from .services import preview_report, send_report_email

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
    """POST /api/reports/training/send/ {kind, date} — gui ngay bao cao qua email
    (REPORT_TO/REPORT_CC), chi Admin/OM."""

    def post(self, request):
        if (request.user.role or '').lower() not in REPORT_ROLES:
            return Response({'detail': 'Bạn không có quyền gửi báo cáo này.'}, status=403)
        kind, ref_date, error = _parse_kind_and_date(request.data)
        if error:
            return Response({'detail': error}, status=400)
        try:
            result = send_report_email(request.user.tenant, kind, ref_date)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result)
