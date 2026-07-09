from rest_framework.permissions import BasePermission


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
