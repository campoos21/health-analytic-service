"""Integration tests for the authentication layer."""

import pytest
from django.test import Client


@pytest.fixture
def client():
    """Return a Django test client."""
    return Client()


class TestApiKeyAuth:
    """Verify that endpoints require a valid active API key."""

    def test_no_key_returns_401(self, client, db):
        """A request without X-API-Key gets 401."""
        resp = client.get("/api/v1/patients/")
        assert resp.status_code == 401

    def test_invalid_key_returns_401(self, client, db):
        """A request with a garbage key gets 401."""
        resp = client.get(
            "/api/v1/patients/",
            HTTP_X_API_Key="totally-invalid-key",
        )
        assert resp.status_code == 401

    def test_inactive_key_returns_401(self, client, inactive_api_key):
        """A request with an inactive key gets 401."""
        resp = client.get(
            "/api/v1/patients/",
            HTTP_X_API_Key=inactive_api_key.key,
        )
        assert resp.status_code == 401

    def test_valid_key_returns_200(self, client, auth_headers, db):
        """A request with a valid active key succeeds."""
        resp = client.get("/api/v1/patients/", **auth_headers)
        assert resp.status_code == 200

    def test_auth_on_records_endpoint(self, client, db):
        """POST /records/ also requires auth."""
        resp = client.post(
            "/api/v1/records/",
            data={"record_id": "REC-NOAUTH"},
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_auth_on_analytics_endpoints(self, client, db):
        """Analytics stubs also require auth."""
        resp1 = client.get("/api/v1/analytics/analytical_endpoint_1")
        resp2 = client.get("/api/v1/analytics/analytical_endpoint_2")
        assert resp1.status_code == 401
        assert resp2.status_code == 401
