class TenantScopedViewSetMixin:
    """Loc queryset theo tenant cua user dang nhap + tu gan tenant khi tao moi."""

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.user.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)
