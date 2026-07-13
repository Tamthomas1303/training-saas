from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import LoginView, MeView, SyncDraftsView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='login_refresh'),
    path('me/', MeView.as_view(), name='me'),
    path('sync/drafts/', SyncDraftsView.as_view(), name='sync-drafts'),
]
