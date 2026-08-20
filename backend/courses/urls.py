from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CourseAssignView,
    CourseModuleViewSet,
    CourseViewSet,
    EnrollmentViewSet,
    LessonViewSet,
    LessonWatchEventView,
    MyCourseDetailView,
    MyCoursesView,
    OfflineConfirmView,
    OfflineReportView,
    ProgressSaveView,
    ReorderView,
    ScormCommitView,
    ScormStateView,
    ScormUploadView,
    scorm_content,
    scorm_player,
    WatchProgressView,
)

router = DefaultRouter()
router.register('modules', CourseModuleViewSet, basename='course-module')
router.register('lessons', LessonViewSet, basename='course-lesson')
router.register('enrollments', EnrollmentViewSet, basename='course-enrollment')
router.register('', CourseViewSet, basename='course')

urlpatterns = [
    path('my/', MyCoursesView.as_view(), name='course-my'),
    path('my/<int:course_id>/', MyCourseDetailView.as_view(), name='course-my-detail'),
    path('progress/', ProgressSaveView.as_view(), name='course-progress'),
    path('watch-progress/', WatchProgressView.as_view(), name='course-watch-progress'),
    path('lesson-watch-event/', LessonWatchEventView.as_view(), name='course-lesson-watch-event'),
    path('reorder/', ReorderView.as_view(), name='course-reorder'),
    path('offline-confirm/', OfflineConfirmView.as_view(), name='course-offline-confirm'),
    path('scorm/upload/', ScormUploadView.as_view(), name='scorm-upload'),
    path('scorm/<int:package_id>/content/<path:path>', scorm_content, name='scorm-content'),
    path('scorm/<int:package_id>/player/', scorm_player, name='scorm-player'),
    path('scorm/<int:progress_id>/state/', ScormStateView.as_view(), name='scorm-state'),
    path('scorm/<int:progress_id>/commit/', ScormCommitView.as_view(), name='scorm-commit'),
    path('<int:pk>/assign/', CourseAssignView.as_view(), name='course-assign'),
    path('<int:pk>/offline-report/', OfflineReportView.as_view(), name='course-offline-report'),
] + router.urls
