from rest_framework import viewsets

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import RestaurantPagination

from .models import Restaurant
from .serializers import RestaurantSerializer


class RestaurantViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = RestaurantSerializer
    queryset = Restaurant.objects.all()
    pagination_class = RestaurantPagination
    filterset_fields = ['brand', 'status', 'city', 'region']
    search_fields = ['code', 'name', 'email']
    ordering_fields = ['code', 'name']
    ordering = ['code']
