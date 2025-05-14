from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserViewSet, CourseViewSet, LessonViewSet,
    GradeViewSet, AttendanceViewSet, GroupViewSet,
    CustomTokenObtainPairView
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'courses', CourseViewSet)
router.register(r'lessons', LessonViewSet)
router.register(r'grades', GradeViewSet)
router.register(r'attendance', AttendanceViewSet)
router.register(r'groups', GroupViewSet)

urlpatterns = [
    path('', include(router.urls)),  # Основной API путь
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('courses/<int:pk>/add-group/', CourseViewSet.as_view({'post': 'add_group'}), name='course-add-group'),
    path('groups/<int:pk>/students/', GroupViewSet.as_view({'get': 'list_students'}), name='group-students'),
    path('groups/<int:pk>/bulk-add-students/', GroupViewSet.as_view({'post': 'bulk_add_students'}), name='group-bulk-add-students'),
]
