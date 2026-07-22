from rest_framework.routers import DefaultRouter

from .views import (
    CohortSessionViewSet,
    CohortViewSet,
    ProgramContentViewSet,
    ProgramViewSet,
)

# M2.2 — chương trình + checklist nội dung + đợt & buổi học. Điểm danh/QR (M2.3), học viên
# (M2.4), thông báo (M2.5) thêm dần.
router = DefaultRouter()
router.register('programs', ProgramViewSet, basename='program')
router.register('program-contents', ProgramContentViewSet, basename='program-content')
router.register('cohorts', CohortViewSet, basename='cohort')
router.register('cohort-sessions', CohortSessionViewSet, basename='cohort-session')

urlpatterns = router.urls
