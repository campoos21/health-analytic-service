"""Integration tests for the analytical stub endpoints."""

import pytest
from django.test import Client


@pytest.fixture
def client():
    """Return a Django test client."""
    return Client()


class TestAnalyticalEndpoint1:
    """GET /api/v1/analytics/analytical_endpoint_1"""

    def test_returns_200(self, client, auth_headers):
        """The stub returns 200 with an empty dict."""
        resp = client.get(
            "/api/v1/analytics/analytical_endpoint_1",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_requires_auth(self, client, db):
        """Without a key the endpoint returns 401."""
        resp = client.get("/api/v1/analytics/analytical_endpoint_1")
        assert resp.status_code == 401


class TestAnalyticalEndpoint2:
    """GET /api/v1/analytics/analytical_endpoint_2"""

    def test_returns_200(self, client, auth_headers):
        """The stub returns 200 with an empty dict."""
        resp = client.get(
            "/api/v1/analytics/analytical_endpoint_2",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == {}

    def test_requires_auth(self, client, db):
        """Without a key the endpoint returns 401."""
        resp = client.get("/api/v1/analytics/analytical_endpoint_2")
        assert resp.status_code == 401
