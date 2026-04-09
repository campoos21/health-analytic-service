"""URL configuration for health_analytic_service project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import path


def healthcheck(request: HttpRequest) -> JsonResponse:
    """Lightweight health-check endpoint used by Docker Compose."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthcheck/", healthcheck, name="healthcheck"),
]

# Serve static files via Django when DEBUG is enabled.
# In production, Nginx (or similar) should serve /static/ directly.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
