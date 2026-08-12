from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CourseAssignView,
    CourseModuleViewSet,
    CourseViewSet,
    EnrollmentViewSet,
    LessonViewSet,
    MyCourseDetailView,
    MyCoursesView,
    ProgressSaveView,
    ReorderView,
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
    path('reorder/', ReorderView.as_view(), name='course-reorder'),
    path('<int:pk>/assign/', CourseAssignView.as_view(), name='course-assign'),
] + router.urls
