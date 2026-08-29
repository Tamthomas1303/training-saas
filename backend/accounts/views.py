import re

from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.mixins import TenantScopedViewSetMixin
from accounts.pagination import DefaultPagination
from restaurants.models import Restaurant

from .models import BrandSettings, PasswordSetToken, PushSubscription, User, UserRestaurantAssignment
from .serializers import (
    BrandSettingsSerializer,
    EmailSettingsSerializer,
    GradingConfigHistorySerializer,
    GradingConfigSerializer,
    RoleMenuConfigHistorySerializer,
    TenantAwareTokenObtainPairSerializer,
    UserAdminSerializer,
    UserSerializer,
)
from .services import (
    archive_user,
    check_user_deletable,
    get_email_settings,
    get_grading_config,
    list_role_menu_config,
    reset_user_password,
    restore_user,
    update_grading_config,
    update_role_menu_config,
)


def _require_admin(request):
    if (request.user.role or '').lower() != 'admin':
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied('Chỉ Admin được thao tác Cài đặt.')


# Prompt_Fix_DotA_29.08.md muc 3 - link Google Drive dang share ".../file/d/<ID>/view?..." KHONG
# phai URL anh truc tiep nen <img> khong tai duoc; tu dong chuyen sang dang "uc?export=view&id=".
_DRIVE_FILE_RE = re.compile(r'drive\.google\.com/file/d/([^/]+)')


def _normalize_logo_url(url):
    match = _DRIVE_FILE_RE.search(url)
    if not match:
        return url
    return f'https://drive.google.com/uc?export=view&id={match.group(1)}'


class LoginView(TokenObtainPairView):
    serializer_class = TenantAwareTokenObtainPairSerializer


class MeView(APIView):

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class BrandSettingsView(APIView):
    """GET /api/settings/brand/ — cau hinh thuong hieu (UI dot 1) cua tenant nguoi dang nhap:
    {system_name, logo_url, brand_hex, theme_mode}. Bat ky tai khoan da dang nhap nao cung doc
    duoc (khong phai man quan tri). Chua co ban ghi (tenant chua cau hinh) -> tra ve gia tri mac
    dinh cua model, KHONG tu tao ban ghi trong DB."""

    def get(self, request):
        settings_obj = (
            BrandSettings.objects.filter(tenant=request.user.tenant).first()
            or BrandSettings(tenant=request.user.tenant)
        )
        return Response(BrandSettingsSerializer(settings_obj).data)

    def put(self, request):
        """PUT — chi Admin. Tao/cap nhat ban ghi BrandSettings cua tenant (khac GET, o day
        THUC SU tao ban ghi trong DB de luu duoc gia tri da chinh).
        Prompt_Fix_DotA_29.08.md muc 3: logo_url gui len co the la (a) data URL (anh upload tu may -
        uu tien, dung lai storage nhu ChangeAvatarView), (b) link Google Drive dang share ("view") -
        tu chuyen sang dang nhung truc tiep, hoac (c) URL thuong - giu nguyen."""
        _require_admin(request)
        from checklist.storage import StorageError, is_data_url, upload_data_url

        settings_obj, _created = BrandSettings.objects.get_or_create(tenant=request.user.tenant)
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        logo_url = (data.get('logo_url') or '').strip()
        if logo_url and is_data_url(logo_url):
            try:
                data['logo_url'] = upload_data_url(
                    logo_url, f'brand-logo/{request.user.tenant_id}', f'logo_{request.user.tenant_id}',
                )
            except StorageError as exc:
                return Response({'detail': str(exc)}, status=400)
        elif logo_url:
            data['logo_url'] = _normalize_logo_url(logo_url)

        serializer = BrandSettingsSerializer(settings_obj, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class GradingConfigView(APIView):
    """GET/PUT /api/settings/grading/ — cau hinh thang danh gia & cong thuc (UI dot 3 muc B).
    Chi Admin (ca doc lan ghi - day la du lieu nhay cam anh huong tinh luong/hoa hong)."""

    def get(self, request):
        _require_admin(request)
        config = get_grading_config(request.user.tenant)
        return Response(GradingConfigSerializer(config).data)

    def put(self, request):
        _require_admin(request)
        current = get_grading_config(request.user.tenant)
        validator = GradingConfigSerializer(current, data=request.data, partial=True)
        validator.is_valid(raise_exception=True)
        config, changed_count = update_grading_config(
            request.user.tenant, request.user, validator.validated_data,
        )
        data = GradingConfigSerializer(config).data
        data['_changed_count'] = changed_count
        return Response(data)


class GradingConfigHistoryView(APIView):
    """GET /api/settings/grading/history/ — lich su thay doi GradingConfig (50 dong gan nhat)."""

    def get(self, request):
        _require_admin(request)
        rows = request.user.tenant.grading_config_history.select_related('changed_by')[:50]
        return Response(GradingConfigHistorySerializer(rows, many=True).data)


class EmailSettingsView(APIView):
    """GET/PUT /api/settings/email/ — nguoi nhan + lich gui bao cao qua email (UI dot 3 muc A2).
    KHONG co truong SMTP/mat khau o day (giu bien moi truong - xem EmailSettings model)."""

    def get(self, request):
        _require_admin(request)
        settings_obj = get_email_settings(request.user.tenant)
        return Response(EmailSettingsSerializer(settings_obj).data)

    def put(self, request):
        _require_admin(request)
        settings_obj = get_email_settings(request.user.tenant)
        serializer = EmailSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class RoleMenuConfigView(APIView):
    """GET/PUT /api/settings/role-menu/ — Muc 16 Phase 1 phan B: BAT/TAT the menu theo vai tro.
    GET: bat ky tai khoan da dang nhap - tra ve {role: [path,...]} CHI cho cac vai tro DA cau
    hinh rieng (vai tro vang mat = "chua cau hinh", frontend tu fallback ve mac dinh hien hanh).
    PUT: chi Admin. Body {role, menu_keys: [path,...]}."""

    def get(self, request):
        return Response(list_role_menu_config(request.user.tenant))

    def put(self, request):
        _require_admin(request)
        role = (request.data.get('role') or '').strip().lower()
        if role not in dict(User.Role.choices):
            return Response({'detail': 'Vai trò không hợp lệ.'}, status=400)
        menu_keys = request.data.get('menu_keys')
        if not isinstance(menu_keys, list):
            return Response({'detail': 'menu_keys phải là danh sách đường dẫn.'}, status=400)
        config, changed = update_role_menu_config(request.user.tenant, request.user, role, menu_keys)
        return Response({'role': config.role, 'menu_keys': config.menu_keys, 'changed': changed})


class RoleMenuConfigHistoryView(APIView):
    """GET /api/settings/role-menu/history/ — lich su thay doi cau hinh menu (50 dong gan nhat)."""

    def get(self, request):
        _require_admin(request)
        rows = request.user.tenant.role_menu_config_history.select_related('changed_by')[:50]
        return Response(RoleMenuConfigHistorySerializer(rows, many=True).data)


class ChangeAvatarView(APIView):
    """POST /api/auth/me/avatar/ — doi anh dai dien cua chinh minh. Body: {avatar: data:...}."""

    def post(self, request):
        from checklist.storage import StorageError, is_data_url, upload_data_url

        value = request.data.get('avatar')
        if not value or not is_data_url(value):
            return Response({'detail': 'Cần ảnh hợp lệ (data URL).'}, status=400)
        try:
            url = upload_data_url(value, f'avatars/{request.user.tenant_id}', f'avatar_{request.user.id}')
        except StorageError as exc:
            return Response({'detail': str(exc)}, status=400)
        request.user.avatar_url = url
        request.user.save(update_fields=['avatar_url'])
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """POST /api/auth/me/change-password/ — doi mat khau cua chinh minh (can dung mat khau cu)."""

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        old_password = request.data.get('old_password') or ''
        new_password = request.data.get('new_password') or ''
        if not request.user.check_password(old_password):
            return Response({'detail': 'Mật khẩu cũ không đúng.'}, status=400)
        try:
            validate_password(new_password, user=request.user)
        except DjangoValidationError as exc:
            return Response({'detail': ' '.join(exc.messages)}, status=400)
        request.user.set_password(new_password)
        # Nhom 1 muc C.3: neu mat khau nay la mat khau tam do Admin reset, doi thanh cong xong
        # thi HET bi ep doi nua (must_change_password=False).
        request.user.must_change_password = False
        request.user.save(update_fields=['password', 'must_change_password'])
        return Response({'detail': 'Đã đổi mật khẩu.'})


class SetPasswordView(APIView):
    """POST /api/auth/set-password/ — man cong khai dat mat khau lan dau (Nhom 3A muc 3,
    Prompt_Nhom3A_Onboarding_TuDong.md), khong can dang nhap (tai khoan onboarding tu dong tao
    ban dau set_unusable_password - xem employees/automation.py). Body: {token, new_password}.
    Token 1 lan (used_at) + het han (PasswordSetToken.expires_at)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.utils import timezone

        raw_token = (request.data.get('token') or '').strip()
        new_password = request.data.get('new_password') or ''
        token = PasswordSetToken.objects.filter(token=raw_token).select_related('user').first()
        if not token:
            return Response({'detail': 'Đường link không hợp lệ.'}, status=400)
        if token.used_at:
            return Response({'detail': 'Đường link này đã được sử dụng.'}, status=400)
        if token.expires_at <= timezone.now():
            return Response({'detail': 'Đường link đã hết hạn.'}, status=400)

        try:
            validate_password(new_password, user=token.user)
        except DjangoValidationError as exc:
            return Response({'detail': ' '.join(exc.messages)}, status=400)

        user = token.user
        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])
        token.used_at = timezone.now()
        token.save(update_fields=['used_at'])
        return Response({'detail': 'Đã đặt mật khẩu. Bạn có thể đăng nhập.'})


class UserViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    """CRUD nguoi dung - man 5.9, chi Admin. Port UserService.gs::upsertUser/listUsers.

    Nhom 1 muc D.1: danh sach mac dinh AN tai khoan da luu tru (archived_at khong null) - truyen
    ?archived=true de xem NGUOC LAI (chi tai khoan da luu tru, dung cho nut "Hien tai khoan da
    luu tru"). Muc C/D con them 3 action rieng: reset-password/archive/restore (huong duoi)."""

    serializer_class = UserAdminSerializer
    # Prompt_Fix_DotA_29.08.md muc 6 (#17b/#17c) - select_related them 'employee'/'employee__
    # restaurant' de UserAdminSerializer.get_restaurant_name/get_position doc ho so nhan su lien
    # ket khong bi N+1 query tren danh sach.
    queryset = User.objects.select_related('restaurant', 'employee', 'employee__restaurant').all()
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

    def get_queryset(self):
        qs = super().get_queryset()
        # Chi loc theo archived_at o danh sach (list) - cac thao tac tren 1 ban ghi cu the
        # (retrieve/update/destroy/reset-password/archive/restore) PHAI tim duoc ca tai khoan DA
        # luu tru (vd /restore/ can lay dung user dang archived_at != null qua get_object()).
        if self.action != 'list':
            return qs
        show_archived = (self.request.query_params.get('archived') or '').lower() == 'true'
        if show_archived:
            return qs.filter(archived_at__isnull=False)
        return qs.filter(archived_at__isnull=True)

    def destroy(self, request, *args, **kwargs):
        """Xoa cung - muc D.2: bat buoc go lai username de xac nhan kep + chan neu da phat sinh
        du lieu nghiep vu (xem accounts.services.check_user_deletable)."""
        user = self.get_object()
        confirm_username = (request.data.get('confirm_username') or '').strip()
        if confirm_username != user.username:
            return Response(
                {'detail': 'Vui lòng gõ đúng tên tài khoản để xác nhận xóa cứng.'}, status=400,
            )
        ok, reason = check_user_deletable(user)
        if not ok:
            return Response({'detail': reason}, status=400)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        """POST /api/auth/users/<id>/reset-password/ — sinh mat khau tam, tra ve HIEN THI 1 LAN
        cho Admin copy dua nguoi dung (khong luu lai dang doc duoc - xem services.reset_user_
        password). Bat co bat buoc doi mat khau o lan dang nhap ke tiep."""
        user = self.get_object()
        password = reset_user_password(user)
        return Response({'username': user.username, 'password': password})

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """POST /api/auth/users/<id>/archive/ — Luu tru (muc D.1): an khoi danh sach mac dinh,
        GIU nguyen du lieu trong DB, khoi phuc duoc qua /restore/."""
        user = archive_user(self.get_object())
        return Response(UserAdminSerializer(user, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """POST /api/auth/users/<id>/restore/ — khoi phuc tai khoan da luu tru."""
        user = restore_user(self.get_object())
        return Response(UserAdminSerializer(user, context=self.get_serializer_context()).data)


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


class VapidPublicKeyView(APIView):
    """GET /api/push/vapid-public-key/ — tra VAPID_PUBLIC_KEY de frontend dung lam
    applicationServerKey khi subscribe (PushManager.subscribe()). Dang nhap moi goi duoc (dung
    permission mac dinh IsAuthenticated - khong can rieng gi them). Chuoi rong neu chua cau hinh
    VAPID (frontend tu bo qua nut 'Bat thong bao day' trong truong hop nay)."""

    def get(self, request):
        from django.conf import settings

        return Response({'vapid_public_key': settings.VAPID_PUBLIC_KEY})


class PushSubscribeView(APIView):
    """POST /api/push/subscribe/ — nhan subscription JSON tu PushManager.subscribe() (frontend),
    luu/khop theo user dang nhap. Body: {endpoint, keys: {p256dh, auth}}. update_or_create theo
    endpoint (duy nhat toan he thong) - subscribe lai (vd trinh duyet tu lam moi) se cap nhat
    thay vi tao trung; dang nhap tai khoan khac tren cung thiet bi se chuyen quyen so huu
    subscription do sang tai khoan moi (dung y nghia: thiet bi dang dang nhap ai thi nhan thay
    cho nguoi do)."""

    def post(self, request):
        endpoint = (request.data.get('endpoint') or '').strip()
        keys = request.data.get('keys') or {}
        p256dh = (keys.get('p256dh') or '').strip()
        auth = (keys.get('auth') or '').strip()
        if not (endpoint and p256dh and auth):
            return Response({'detail': 'Thiếu endpoint/keys.'}, status=400)
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user, 'p256dh': p256dh, 'auth': auth,
                'user_agent': (request.META.get('HTTP_USER_AGENT') or '')[:255],
            },
        )
        return Response({'detail': 'Đã bật thông báo đẩy.'})


class PushUnsubscribeView(APIView):
    """POST /api/push/unsubscribe/ — xoa 1 subscription theo endpoint. Body: {endpoint}. Chi xoa
    neu subscription do THUOC VE user dang goi (khong cho xoa ho subscription cua nguoi khac)."""

    def post(self, request):
        endpoint = (request.data.get('endpoint') or '').strip()
        if not endpoint:
            return Response({'detail': 'Thiếu endpoint.'}, status=400)
        PushSubscription.objects.filter(endpoint=endpoint, user=request.user).delete()
        return Response({'detail': 'Đã tắt thông báo đẩy.'})
