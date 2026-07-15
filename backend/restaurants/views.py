from rest_framework import viewsets

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import RestaurantPagination

from .models import Restaurant
from .serializers import RestaurantSerializer


class RestaurantViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD nha hang. Doc: moi role dang nhap (vd bo loc trong man Nhan su/KPI). Ghi (them/
    sua/xoa): chi Admin - quan tri gop vao man Nguoi dung (muc 4, sprint UI Dot 3), giong
    ban goc (RestaurantService.gs::upsert chi Admin)."""

    serializer_class = RestaurantSerializer
    queryset = Restaurant.objects.all()
    pagination_class = RestaurantPagination
    filterset_fields = ['brand', 'status', 'city', 'region']
    search_fields = ['code', 'name', 'email']
    ordering_fields = ['code', 'name']
    ordering = ['code']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and (request.user.role or '').lower() != 'admin':
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Chỉ Admin được thêm/sửa/xóa nhà hàng.')
