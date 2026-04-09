"""API key authentication for Django Ninja with in-memory caching."""

import logging
from typing import Any, Optional

from django.core.cache import cache
from django.http import HttpRequest
from ninja.security import APIKeyHeader

from health_analytic_service.models import ApiKey

logger = logging.getLogger(__name__)

# Cache TTL in seconds for valid API key lookups.
_API_KEY_CACHE_TTL = 60


class ApiKeyAuth(APIKeyHeader):
    """Authenticate requests via the ``X-API-Key`` header.

    Looks up an active :class:`~health_analytic_service.models.ApiKey` row.
    Results are cached for ``_API_KEY_CACHE_TTL`` seconds to avoid a DB
    query on every request.

    On success the ``ApiKey`` instance is assigned to ``request.auth`` so that
    :class:`~ninja.throttling.AuthRateThrottle` can throttle per-key.
    """

    param_name = "X-API-Key"

    def authenticate(self, request: HttpRequest, key: Optional[str]) -> Any:
        """Return the ApiKey instance if *key* is valid, else ``None``."""
        if key is None:
            return None

        cache_key = f"apikey:{key}"
        cached = cache.get(cache_key)

        if cached is not None:
            # cached == False means "we looked this key up and it was invalid".
            if cached is False:
                return None
            return cached

        try:
            api_key = ApiKey.objects.get(key=key, is_active=True)
        except ApiKey.DoesNotExist:
            cache.set(cache_key, False, _API_KEY_CACHE_TTL)
            return None

        cache.set(cache_key, api_key, _API_KEY_CACHE_TTL)
        return api_key
