from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangeAvatarView,
    ChangePasswordView,
    LoginView,
    MeView,
    SyncDraftsView,
    UserAreasView,
    UserViewSet,
)

router = DefaultRouter()
router.register('users', UserViewSet, basename='user')

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='login_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('me/avatar/', ChangeAvatarView.as_view(), name='me-avatar'),
    path('me/change-password/', ChangePasswordView.as_view(), name='me-change-password'),
    path('sync/drafts/', SyncDraftsView.as_view(), name='sync-drafts'),
    path('users/<int:pk>/areas/', UserAreasView.as_view(), name='user-areas'),
] + router.urls
