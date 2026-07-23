from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendCheckInView,
    AttendInfoView,
    CohortBulkEnrollView,
    CohortReportView,
    CohortSessionViewSet,
    CohortViewSet,
    EnrollmentContentsView,
    EnrollmentResultView,
    EnrollmentViewSet,
    EventCheckInView,
    EventInfoView,
    NotificationListView,
    ProgramContentViewSet,
    ProgramViewSet,
    SessionAttendanceView,
)

# M2.2 — chương trình + checklist nội dung + đợt & buổi học. M2.3 — điểm danh (QR tự quét +
# điều chỉnh tay). Học viên (M2.4), thông báo (M2.5) thêm dần.
router = DefaultRouter()
router.register('programs', ProgramViewSet, basename='program')
router.register('program-contents', ProgramContentViewSet, basename='program-content')
router.register('cohorts', CohortViewSet, basename='cohort')
router.register('cohort-sessions', CohortSessionViewSet, basename='cohort-session')
router.register('enrollments', EnrollmentViewSet, basename='enrollment')

urlpatterns = [
    path('cohort-sessions/<int:pk>/attendance/', SessionAttendanceView.as_view(), name='session-attendance'),
    path('enrollments/<int:pk>/contents/', EnrollmentContentsView.as_view(), name='enrollment-contents'),
    path('enrollments/<int:pk>/result/', EnrollmentResultView.as_view(), name='enrollment-result'),
    path('notifications/', NotificationListView.as_view(), name='notifications'),
    path('attend/<str:token>/', AttendInfoView.as_view(), name='attend-info'),
    path('attend/<str:token>/checkin/', AttendCheckInView.as_view(), name='attend-checkin'),
    path('cohorts/<int:pk>/bulk-enroll/', CohortBulkEnrollView.as_view(), name='cohort-bulk-enroll'),
    path('cohorts/<int:pk>/report/', CohortReportView.as_view(), name='cohort-report'),
    path('event/<str:token>/', EventInfoView.as_view(), name='event-info'),
    path('event/<str:token>/checkin/', EventCheckInView.as_view(), name='event-checkin'),
] + router.urls
