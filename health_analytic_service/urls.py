"""URL configuration for health_analytic_service project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import path

from health_analytic_service.api import api


def healthcheck(request: HttpRequest) -> JsonResponse:
    """Lightweight health-check endpoint used by Docker Compose."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthcheck/", healthcheck, name="healthcheck"),
    path("api/v1/", api.urls),
]

# Serve static files via Django when DEBUG is enabled.
# In production, Nginx (or similar) should serve /static/ directly.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
