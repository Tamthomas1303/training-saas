# Buoc 1 (Prompt_KhungNoiDung_CapO_Buoc1.md muc 2) - API rieng duoi "/api/curriculum/" (KHONG
# nam duoi "/api/employees/" nhu phan lon employees/urls.py, dung DUNG duong dan prompt yeu cau).
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import CurriculumBulkAssignView, CurriculumItemViewSet

# SimpleRouter (KHONG dung DefaultRouter) vi CurriculumItemViewSet dang ky o prefix RONG ('') -
# DefaultRouter se tu sinh them 1 "API root view" rieng cung khop pattern '^$', chong len chinh
# list-view cua ViewSet (bai hoc tu Prompt_Fix_TrangTrang_MapUndefined.md, xem employees/urls.py).
router = SimpleRouter()
router.register('', CurriculumItemViewSet, basename='curriculum-item')

urlpatterns = [
    # Dat TRUOC router.urls - "bulk/" se bi pattern '^(?P<pk>[^/.]+)/$' cua ViewSet (prefix rong)
    # nuot mat neu dat SAU (cung ly do voi automation_router trong employees/urls.py).
    path('bulk/', CurriculumBulkAssignView.as_view(), name='curriculum-bulk'),
] + router.urls
