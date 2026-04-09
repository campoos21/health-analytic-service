"""API key authentication for Django Ninja."""

from typing import Any, Optional

from django.http import HttpRequest
from ninja.security import APIKeyHeader

from health_analytic_service.models import ApiKey


class ApiKeyAuth(APIKeyHeader):
    """Authenticate requests via the ``X-API-Key`` header.

    Looks up an active :class:`~health_analytic_service.models.ApiKey` row.
    On success the ``ApiKey`` instance is assigned to ``request.auth`` so that
    :class:`~ninja.throttling.AuthRateThrottle` can throttle per-key.
    """

    param_name = "X-API-Key"

    def authenticate(self, request: HttpRequest, key: Optional[str]) -> Any:
        """Return the ApiKey instance if *key* is valid, else ``None``."""
        if key is None:
            return None
        try:
            return ApiKey.objects.get(key=key, is_active=True)
        except ApiKey.DoesNotExist:
            return None
