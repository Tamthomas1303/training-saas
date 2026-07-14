from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.pagination import DefaultPagination
from checklist.models import Document

from .models import Commission
from .serializers import CommissionSerializer, KpiSessionSerializer, KpiTopicSerializer
from .services import (
    ValidationError,
    allowance_report_data,
    commission_queryset_for_user,
    generate_allowance_pdf,
    generate_kpi_report_pdf,
    kpi_bql_report_data,
    kpi_queryset_for_user,
    kpi_stats,
    mark_commission_paid,
    recompute_all_commissions,
    save_kpi_session,
)

REPORT_ROLES = {'admin', 'om'}


def _parse_month_year(request):
    from django.utils import timezone

    now = timezone.now()
    month = int(request.query_params.get('month') or now.month)
    year = int(request.query_params.get('year') or now.year)
    return month, year


class KpiTopicsView(APIView):
    """GET /api/kpi/topics/ — danh muc chu de dao tao chuan (tu Document), dung cho datalist.
    Port KPIService.gs::topics (DB_Document)."""


    def get(self, request):
        docs = Document.objects.filter(tenant=request.user.tenant).order_by('name')
        return Response(KpiTopicSerializer(docs, many=True).data)


class KpiSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """Danh sach buoi KPI da ghi - chi doc (tao qua KpiSessionSaveView), loc theo pham vi
    nha hang cua user + filter restaurant, phan trang."""

    serializer_class = KpiSessionSerializer
    pagination_class = DefaultPagination
    filterset_fields = ['restaurant']
    search_fields = ['topic']
    ordering_fields = ['date']
    ordering = ['-date']

    def get_queryset(self):
        return kpi_queryset_for_user(self.request.user).select_related('restaurant', 'trainer')


class KpiSessionSaveView(APIView):

    def post(self, request):
        try:
            session = save_kpi_session(request.user, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(KpiSessionSerializer(session).data)


class KpiStatsView(APIView):

    def get(self, request):
        return Response(kpi_stats(request.user))


class CommissionListView(APIView):

    def get(self, request):
        qs = commission_queryset_for_user(request.user).order_by('-updated_at')
        month = request.query_params.get('month')
        year = request.query_params.get('year')
        if month:
            qs = qs.filter(month=month)
        if year:
            qs = qs.filter(year=year)
        return Response(CommissionSerializer(qs, many=True).data)


class CommissionMarkPaidView(APIView):

    def post(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được đánh dấu đã chi.'}, status=403)
        commission = get_object_or_404(Commission, pk=pk, tenant=request.user.tenant)
        mark_commission_paid(commission)
        return Response(CommissionSerializer(commission).data)


class CommissionRecomputeAllView(APIView):

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được tính lại toàn bộ hoa hồng.'}, status=403)
        processed = recompute_all_commissions(request.user.tenant)
        return Response({'processed': processed})


class KpiReportDataView(APIView):
    """GET /api/kpi/report/?month=&year= — so lieu 'Bao cao KPI BQL' theo thang, chi Admin/OM."""


    def get(self, request):
        if (request.user.role or '').lower() not in REPORT_ROLES:
            return Response({'detail': 'Bạn không có quyền xem báo cáo này.'}, status=403)
        month, year = _parse_month_year(request)
        return Response(kpi_bql_report_data(request.user, month, year))


class KpiReportExportView(APIView):
    """POST /api/kpi/report/export/?month=&year= — xuat PDF 'Bao cao KPI BQL', chi Admin/OM."""


    def post(self, request):
        if (request.user.role or '').lower() not in REPORT_ROLES:
            return Response({'detail': 'Bạn không có quyền xuất báo cáo này.'}, status=403)
        month, year = _parse_month_year(request)
        pdf_url = generate_kpi_report_pdf(request.user, month, year)
        return Response({'pdf_url': pdf_url})


class AllowanceDataView(APIView):
    """GET /api/kpi/allowance/?month=&year= — danh sach phu cap trainer, chi Admin/OM."""


    def get(self, request):
        if (request.user.role or '').lower() not in REPORT_ROLES:
            return Response({'detail': 'Bạn không có quyền xem phụ cấp trainer.'}, status=403)
        month, year = _parse_month_year(request)
        return Response(allowance_report_data(request.user, month, year))


class AllowanceExportView(APIView):
    """POST /api/kpi/allowance/export/?month=&year= — xuat PDF 'Phieu phu cap trainer', chi
    Admin/OM."""


    def post(self, request):
        if (request.user.role or '').lower() not in REPORT_ROLES:
            return Response({'detail': 'Bạn không có quyền xuất phiếu phụ cấp.'}, status=403)
        month, year = _parse_month_year(request)
        pdf_url = generate_allowance_pdf(request.user, month, year)
        return Response({'pdf_url': pdf_url})
