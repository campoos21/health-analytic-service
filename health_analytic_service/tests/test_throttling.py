"""Integration tests for throttling / rate limiting."""

import pytest
from django.test import Client as DjangoTestClient
from ninja import NinjaAPI, Router
from ninja.throttling import AuthRateThrottle


class TestThrottling:
    """Verify that rate limiting kicks in after exceeding the threshold."""

    def test_rate_limit_exceeded(self, api_key):
        """After exceeding the rate limit, the server returns 429.

        We create a standalone NinjaAPI with a very low rate (2/min),
        mount it at a temporary URL, and verify that the 3rd+ requests
        get a 429 Too Many Requests response.
        """
        from django.test.utils import override_settings
        from django.urls import clear_url_caches, path

        throttled_api = NinjaAPI(
            urls_namespace="throttle_test",
            throttle=[AuthRateThrottle("2/min")],
        )

        @throttled_api.get("/test")
        def test_view(request):
            return {"ok": True}

        # Temporarily override ROOT_URLCONF to include our throttled API
        test_urlpatterns = [
            path("throttle-test/", throttled_api.urls),
        ]

        import types
        test_urls = types.ModuleType("test_throttle_urls")
        test_urls.urlpatterns = test_urlpatterns

        import sys
        sys.modules["test_throttle_urls"] = test_urls

        with override_settings(ROOT_URLCONF="test_throttle_urls"):
            clear_url_caches()
            client = DjangoTestClient()

            statuses = []
            for _ in range(5):
                resp = client.get("/throttle-test/test")
                statuses.append(resp.status_code)

            clear_url_caches()

        del sys.modules["test_throttle_urls"]

        assert statuses[0] == 200
        assert statuses[1] == 200
        assert 429 in statuses[2:]
