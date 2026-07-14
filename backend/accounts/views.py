from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination
from restaurants.models import Restaurant

from .models import User, UserRestaurantAssignment
from .serializers import TenantAwareTokenObtainPairSerializer, UserAdminSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = TenantAwareTokenObtainPairSerializer


class MeView(APIView):

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD nguoi dung - man 5.9, chi Admin. Port UserService.gs::upsertUser/listUsers."""

    serializer_class = UserAdminSerializer
    queryset = User.objects.select_related('restaurant').all()
    pagination_class = DefaultPagination
    filterset_fields = ['role', 'status', 'restaurant']
    search_fields = ['username', 'full_name']
    ordering_fields = ['username', 'full_name']
    ordering = ['username']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method != 'OPTIONS' and (request.user.role or '').lower() != 'admin':
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Chỉ Admin được quản trị người dùng.')


class UserAreasView(APIView):
    """GET/POST /api/auth/users/<id>/areas/ — "Phan vung" cho KCS (nhieu nha hang). Port
    UserService.gs::getUserAreas/setUserAreas."""


    def get(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được xem phân vùng.'}, status=403)
        user = get_object_or_404(User, pk=pk, tenant=request.user.tenant)
        ids = list(user.restaurant_assignments.values_list('restaurant_id', flat=True))
        return Response({'restaurant_ids': ids})

    def post(self, request, pk):
        if (request.user.role or '').lower() != 'admin':
            return Response({'detail': 'Chỉ Admin được gán phân vùng.'}, status=403)
        user = get_object_or_404(User, pk=pk, tenant=request.user.tenant)
        restaurant_ids = request.data.get('restaurant_ids') or []
        restaurants = Restaurant.objects.filter(tenant=request.user.tenant, id__in=restaurant_ids)
        UserRestaurantAssignment.objects.filter(user=user).delete()
        UserRestaurantAssignment.objects.bulk_create([
            UserRestaurantAssignment(user=user, restaurant=r) for r in restaurants
        ])
        return Response({'restaurant_ids': [r.id for r in restaurants]})


class SyncDraftsView(APIView):
    """POST /api/auth/sync/drafts/ — nhan hang doi nhap offline tu client (IndexedDB) khi co
    mang tro lai. Port SyncService.gs::flush. Body: [{kind:'training'|'evaluation', payload:{...},
    client_uuid}, ...]. Tra ve [{client_uuid, ok, message?}, ...] de client biet muc nao da dong
    bo xong (xoa khoi hang doi) va muc nao con loi (giu lai)."""


    def post(self, request):
        from checklist.services import ValidationError as ChecklistValidationError
        from checklist.services import save_training_progress
        from evaluation.services import ValidationError as EvaluationValidationError
        from evaluation.services import save_evaluation
        from kpi.services import ValidationError as KpiValidationError
        from kpi.services import save_kpi_session

        items = request.data if isinstance(request.data, list) else request.data.get('items', [])
        results = []
        for item in items:
            kind = item.get('kind')
            payload = item.get('payload') or {}
            client_uuid = item.get('client_uuid')
            try:
                if kind == 'training':
                    save_training_progress(request.user, payload)
                elif kind == 'evaluation':
                    save_evaluation(request.user, payload)
                elif kind == 'kpi':
                    save_kpi_session(request.user, payload)
                else:
                    raise ValueError(f'Loại nháp không hỗ trợ: {kind}')
                results.append({'client_uuid': client_uuid, 'ok': True})
            except (ChecklistValidationError, EvaluationValidationError, KpiValidationError, ValueError) as exc:
                results.append({'client_uuid': client_uuid, 'ok': False, 'message': str(exc)})

        return Response({'results': results})
