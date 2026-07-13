from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import TenantAwareTokenObtainPairSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = TenantAwareTokenObtainPairSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class SyncDraftsView(APIView):
    """POST /api/auth/sync/drafts/ — nhan hang doi nhap offline tu client (IndexedDB) khi co
    mang tro lai. Port SyncService.gs::flush. Body: [{kind:'training'|'evaluation', payload:{...},
    client_uuid}, ...]. Tra ve [{client_uuid, ok, message?}, ...] de client biet muc nao da dong
    bo xong (xoa khoi hang doi) va muc nao con loi (giu lai)."""

    permission_classes = [IsAuthenticated]

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
