from django.contrib import admin
from django.urls import path, include
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Gradar API",
        default_version='v1',
        description="API для системы управления учебным процессом Gradar. "
                  "Позволяет управлять курсами, группами студентов, занятиями, "
                  "оценками и посещаемостью.",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="support@gradar.edu"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
]
