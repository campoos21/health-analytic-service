"""Shared fixtures for analytics tests."""

import pytest

from health_analytic_service.models import ApiKey


@pytest.fixture
def api_key(db):
    """Create and return an active API key."""
    return ApiKey.objects.create(name="analytics-test-key", key="analytics-key-12345")


@pytest.fixture
def auth_headers(api_key):
    """Return a dict with the X-API-Key header set."""
    return {"HTTP_X_API_Key": api_key.key}
