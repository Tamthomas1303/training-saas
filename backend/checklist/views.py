from rest_framework import viewsets

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination

from .models import Checklist
from .serializers import ChecklistSerializer


class ChecklistViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ChecklistSerializer
    queryset = Checklist.objects.all()
    pagination_class = DefaultPagination
    filterset_fields = ['brand', 'position', 'level_group', 'category']
    search_fields = ['task_name', 'description']
    ordering_fields = ['order', 'day']
    ordering = ['order']
