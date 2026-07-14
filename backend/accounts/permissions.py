from rest_framework.permissions import SAFE_METHODS, BasePermission


class BodReadOnly(BasePermission):
    """BOD (Ban Giam doc) chi xem - chan moi thao tac ghi (POST/PUT/PATCH/DELETE) tren toan
    bo API. Ap dung toan cuc qua DEFAULT_PERMISSION_CLASSES de dam bao "moi man" deu bi
    chan, khong can sua tung view rieng le - dung tinh than muc 6 ban thiet ke ("BOD read-only:
    o moi man, khi vai tro la BOD thi an toan bo nut thao tac/xuat/chot")."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return (getattr(request.user, 'role', '') or '').lower() != 'bod'


class IsSameTenant(BasePermission):
    """Chỉ cho phép thao tác trên object cùng tenant với user đang đăng nhập."""

    def has_object_permission(self, request, view, obj):
        tenant_id = getattr(obj, 'tenant_id', None)
        return tenant_id is not None and tenant_id == request.user.tenant_id


class HasRole(BasePermission):
    """Dùng qua HasRole.for_roles('admin', 'om') làm permission_classes cho view."""

    allowed_roles: tuple = ()

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )

    @classmethod
    def for_roles(cls, *roles):
        return type('HasRoleDynamic', (cls,), {'allowed_roles': roles})
