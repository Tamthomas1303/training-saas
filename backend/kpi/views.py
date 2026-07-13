from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.pagination import DefaultPagination
from checklist.models import Document

from .models import Commission
from .serializers import CommissionSerializer, KpiSessionSerializer, KpiTopicSerializer
from .services import (
    ValidationError,
    commission_queryset_for_user,
    kpi_queryset_for_user,
    kpi_stats,
    mark_commission_paid,
    recompute_all_commissions,
    save_kpi_session,
)


class KpiTopicsView(APIView):
    """GET /api/kpi/topics/ — danh muc chu de dao tao chuan (tu Document), dung cho datalist.
    Port KPIService.gs::topics (DB_Document)."""

    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            session = save_kpi_session(request.user, request.data)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(KpiSessionSerializer(session).data)


class KpiStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(kpi_stats(request.user))


class CommissionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = commission_queryset_for_user(request.user).order_by('-updated_at')
        return Response(CommissionSerializer(qs, many=True).data)


class CommissionMarkPaidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được đánh dấu đã chi.'}, status=403)
        commission = get_object_or_404(Commission, pk=pk, tenant=request.user.tenant)
        mark_commission_paid(commission)
        return Response(CommissionSerializer(commission).data)


class CommissionRecomputeAllView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được tính lại toàn bộ hoa hồng.'}, status=403)
        processed = recompute_all_commissions(request.user.tenant)
        return Response({'processed': processed})
