from django.db.models import Q
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination
from employees.models import Employee

from .models import CompetencyGroup, Competency, DashboardIndicator, PositionGroupWeight, PositionTarget
from .serializers import (
    CompetencyGroupSerializer,
    CompetencySerializer,
    DashboardIndicatorSerializer,
    PositionGroupWeightSerializer,
    PositionTargetSerializer,
)
from .services import (
    ValidationError,
    employee_360,
    import_position_group_weights,
    import_position_targets,
    seed_competency_framework,
    seed_dashboard_indicators,
)

# "CEO/GĐĐT/HR" (prompt) anh xa sang vai tro co san cua he thong nay: admin, bod (Ban giam
# doc = CEO), om (dang dung cho bao cao/dashboard quan tri = GĐĐT/HR). Cac vai tro van hanh
# diem (am/kcs/bql/trainer) va hoc vien KHONG xem duoc Ho so 360/cau hinh Dashboard.
DASHBOARD_VIEW_ROLES = {'admin', 'om', 'bod'}


def _require_dashboard_view(request):
    if (request.user.role or '').lower() not in DASHBOARD_VIEW_ROLES:
        raise PermissionDenied('Bạn không có quyền xem Dashboard/Hồ sơ 360.')


def _require_admin_write(request):
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and (request.user.role or '').lower() != 'admin':
        raise PermissionDenied('Chỉ Admin được sửa cấu hình khung năng lực/Dashboard.')


class CompetencyGroupViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD nhom nang luc. Doc: admin/om/bod. Ghi: chi Admin."""

    serializer_class = CompetencyGroupSerializer
    queryset = CompetencyGroup.objects.all()
    pagination_class = DefaultPagination
    ordering = ['order']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_dashboard_view(request)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class CompetencyViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD nang luc. Loc theo group=<id>. Doc: admin/om/bod. Ghi: chi Admin."""

    serializer_class = CompetencySerializer
    queryset = Competency.objects.select_related('group').all()
    pagination_class = DefaultPagination
    filterset_fields = ['group']
    ordering = ['order']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_dashboard_view(request)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class PositionTargetViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD diem muc tieu theo vi tri. Loc theo position=, competency=. Doc: admin/om/bod.
    Ghi: chi Admin (thuong dung Import CSV, CRUD tung dong chi de sua nhanh 1 o)."""

    serializer_class = PositionTargetSerializer
    queryset = PositionTarget.objects.select_related('competency', 'competency__group').all()
    pagination_class = DefaultPagination
    filterset_fields = ['position', 'competency']
    ordering = ['position']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_dashboard_view(request)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class PositionGroupWeightViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD trong so nhom theo vi tri. Doc: admin/om/bod. Ghi: chi Admin."""

    serializer_class = PositionGroupWeightSerializer
    queryset = PositionGroupWeight.objects.select_related('group').all()
    pagination_class = DefaultPagination
    filterset_fields = ['position', 'group']
    ordering = ['position']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_dashboard_view(request)
        _require_admin_write(request)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class DashboardIndicatorViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """Cau hinh chi so Dashboard (Phan A muc 5) - bat/tat + doi vai tro hien thi + nguong mau.
    Doc: admin/om/bod. Ghi (PATCH bat/tat/nguong): chi Admin. Khong cho tao/xoa chi so qua API
    (danh sach co dinh tu seed, chi tao/xoa qua management command neu can mo rong)."""

    serializer_class = DashboardIndicatorSerializer
    queryset = DashboardIndicator.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['enabled']
    ordering = ['order']
    http_method_names = ['get', 'patch', 'head', 'options']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_dashboard_view(request)
        _require_admin_write(request)


class SeedDefaultsView(APIView):
    """POST /api/dashboard/seed-defaults/ — seed 6 nhóm + 24 năng lực khởi điểm (mục 1) và danh
    sách chỉ số Dashboard đã chọn (mục 5). Idempotent - bấm lại không tạo trùng. Chỉ Admin."""

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được khởi tạo cấu hình mặc định.'}, status=403)
        framework = seed_competency_framework(request.user.tenant)
        indicators = seed_dashboard_indicators(request.user.tenant)
        return Response({**framework, **indicators})


class ImportPositionTargetsView(APIView):
    """POST /api/dashboard/import/targets/ — multipart {file: <CSV>} xuất từ sheet 'Muc tieu
    theo vi tri' (KhungNangLuc_MucTieu_TheoViTri_v0.5.xlsx). Chỉ Admin."""

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được import khung năng lực.'}, status=403)
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': "Cần file CSV ('file')."}, status=400)
        try:
            text = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'detail': 'File CSV cần mã hoá UTF-8.'}, status=400)
        try:
            result = import_position_targets(request.user.tenant, text)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result)


class ImportPositionGroupWeightsView(APIView):
    """POST /api/dashboard/import/weights/ — multipart {file: <CSV>} xuất từ sheet 'Trong so
    nhom'. Chỉ Admin."""

    def post(self, request):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được import trọng số nhóm.'}, status=403)
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': "Cần file CSV ('file')."}, status=400)
        try:
            text = upload.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            return Response({'detail': 'File CSV cần mã hoá UTF-8.'}, status=400)
        try:
            result = import_position_group_weights(request.user.tenant, text)
        except ValidationError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(result)


class EmployeeSearchView(APIView):
    """GET /api/dashboard/employees/?q=... — tìm nhân sự theo tên/mã cho thanh tìm kiếm Hồ sơ
    360. Admin/om/bod."""

    def get(self, request):
        _require_dashboard_view(request)
        q = (request.query_params.get('q') or '').strip()
        qs = Employee.objects.filter(tenant=request.user.tenant)
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        qs = qs.select_related('restaurant').order_by('name')[:20]
        return Response([
            {
                'id': e.id, 'code': e.code, 'name': e.name, 'position': e.position,
                'restaurant': e.restaurant.name if e.restaurant_id else '',
            }
            for e in qs
        ])


class Employee360View(APIView):
    """GET /api/dashboard/employee/<id_or_code>/ — gói dữ liệu Hồ sơ 360 (mục 4). Admin/om/bod."""

    def get(self, request, id_or_code):
        _require_dashboard_view(request)
        tenant = request.user.tenant
        employee = None
        if str(id_or_code).isdigit():
            employee = Employee.objects.filter(tenant=tenant, pk=id_or_code).select_related('restaurant').first()
        if not employee:
            employee = Employee.objects.filter(tenant=tenant, code__iexact=id_or_code).select_related('restaurant').first()
        if not employee:
            return Response({'detail': 'Không tìm thấy nhân sự.'}, status=404)
        return Response(employee_360(employee))
