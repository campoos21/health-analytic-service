"""Integration tests for the analytical endpoints.

Endpoint 1 – ``GET /api/v1/analytics/visit-durations``
Endpoint 2 – ``GET /api/v1/analytics/incomplete-visits``
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest
from django.test import Client

from analytics.models import Visit
from health_analytic_service.models import Patient

# ─── Helpers ─────────────────────────────────────────────────────────────────

BASE = datetime(2026, 4, 1, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def client() -> Client:
    """Return a Django test client."""
    return Client()


@pytest.fixture
def _completed_visits(patient: Patient) -> list[Visit]:
    """Create three completed visits with known durations.

    Visit 1: 1 h (3 600 s)  – registration Apr 1 08:00
    Visit 2: 2 h (7 200 s)  – registration Apr 2 08:00
    Visit 3: 0.5 h (1 800 s) – registration Apr 3 08:00
    """
    visits = []
    for day_offset, hours in [(0, 1), (1, 2), (2, 0.5)]:
        reg = BASE + timedelta(days=day_offset)
        dep = reg + timedelta(hours=hours)
        visits.append(
            Visit.objects.create(
                patient=patient,
                registration_at=reg,
                departure_at=dep,
                status=Visit.Status.COMPLETED,
                is_registration_missing=False,
                is_departure_missing=False,
            )
        )
    return visits


@pytest.fixture
def _incomplete_visits(patient: Patient) -> list[Visit]:
    """Create two incomplete visits.

    Visit A: IN_PROGRESS, has registration, missing departure.
    Visit B: IN_PROGRESS, missing registration (no registration_at).
    """
    a = Visit.objects.create(
        patient=patient,
        registration_at=BASE,
        status=Visit.Status.IN_PROGRESS,
        is_registration_missing=False,
        is_departure_missing=True,
    )
    b = Visit.objects.create(
        patient=patient,
        status=Visit.Status.IN_PROGRESS,
        is_registration_missing=True,
        is_departure_missing=True,
    )
    return [a, b]


# ─── Endpoint 1: visit-durations ────────────────────────────────────────────


class TestVisitDurations:
    """GET /api/v1/analytics/visit-durations."""

    URL = "/api/v1/analytics/visit-durations"

    def test_requires_auth(self, client: Client, db: Any) -> None:
        """Without a key the endpoint returns 401."""
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_returns_completed_visits(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _completed_visits: list[Visit],
    ) -> None:
        """Returns all completed visits with correct durations."""
        resp = client.get(self.URL, **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3
        assert len(data["results"]) == 3

        # Durations sorted by -registration_at → visit3, visit2, visit1
        durations = [r["duration_seconds"] for r in data["results"]]
        assert durations == [1800, 7200, 3600]

    def test_excludes_incomplete_visits(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _incomplete_visits: list[Visit],
    ) -> None:
        """Incomplete visits must not appear in the duration endpoint."""
        resp = client.get(self.URL, **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["results"] == []

    def test_date_from_filter(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _completed_visits: list[Visit],
    ) -> None:
        """date_from excludes visits registered before the threshold."""
        date_from = (BASE + timedelta(days=1)).isoformat()
        resp = client.get(self.URL, {"date_from": date_from}, **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2  # visit2 and visit3

    def test_date_to_filter(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _completed_visits: list[Visit],
    ) -> None:
        """date_to excludes visits registered after the threshold."""
        date_to = (BASE + timedelta(days=1)).isoformat()
        resp = client.get(self.URL, {"date_to": date_to}, **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 2  # visit1 and visit2

    def test_date_range_filter(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _completed_visits: list[Visit],
    ) -> None:
        """Combining date_from and date_to narrows the result set."""
        date_from = (BASE + timedelta(days=1)).isoformat()
        date_to = (BASE + timedelta(days=1)).isoformat()
        resp = client.get(
            self.URL, {"date_from": date_from, "date_to": date_to}, **auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["count"] == 1  # only visit2

    def test_pagination_offset_limit(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _completed_visits: list[Visit],
    ) -> None:
        """Offset/limit correctly pages through results."""
        resp = client.get(self.URL, {"offset": 0, "limit": 2}, **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 3  # total stays the same
        assert len(data["results"]) == 2  # only 2 returned

        resp2 = client.get(self.URL, {"offset": 2, "limit": 2}, **auth_headers)
        data2 = resp2.json()
        assert data2["count"] == 3
        assert len(data2["results"]) == 1  # remaining 1

    def test_response_schema_fields(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _completed_visits: list[Visit],
    ) -> None:
        """Each result contains the expected fields."""
        resp = client.get(self.URL, {"limit": 1}, **auth_headers)
        result = resp.json()["results"][0]
        assert "id" in result
        assert "patient_id" in result
        assert "registration_at" in result
        assert "departure_at" in result
        assert "duration_seconds" in result
        assert isinstance(result["duration_seconds"], int)


# ─── Endpoint 2: incomplete-visits ──────────────────────────────────────────


class TestIncompleteVisits:
    """GET /api/v1/analytics/incomplete-visits."""

    URL = "/api/v1/analytics/incomplete-visits"

    def test_requires_auth(self, client: Client, db: Any) -> None:
        """Without a key the endpoint returns 401."""
        resp = client.get(self.URL)
        assert resp.status_code == 401

    def test_returns_incomplete_visits(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _incomplete_visits: list[Visit],
    ) -> None:
        """Returns all non-completed visits."""
        resp = client.get(self.URL, **auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2

    def test_excludes_completed_visits(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _completed_visits: list[Visit],
    ) -> None:
        """Completed visits must not appear in the incomplete endpoint."""
        resp = client.get(self.URL, **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_flags_present(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _incomplete_visits: list[Visit],
    ) -> None:
        """Each result exposes the missing-boundary flags."""
        resp = client.get(self.URL, **auth_headers)
        for result in resp.json()["results"]:
            assert "is_registration_missing" in result
            assert "is_departure_missing" in result
            assert "status" in result

    def test_date_from_filter(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _incomplete_visits: list[Visit],
    ) -> None:
        """date_from filters on registration_at – visit without reg is excluded."""
        # Only visit A has registration_at = BASE
        date_from = BASE.isoformat()
        resp = client.get(self.URL, {"date_from": date_from}, **auth_headers)
        assert resp.status_code == 200
        # Visit B has no registration_at → excluded by gte filter
        assert resp.json()["count"] == 1

    def test_pagination(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _incomplete_visits: list[Visit],
    ) -> None:
        """Offset/limit pagination works correctly."""
        resp = client.get(self.URL, {"offset": 0, "limit": 1}, **auth_headers)
        data = resp.json()
        assert data["count"] == 2
        assert len(data["results"]) == 1

    def test_response_schema_fields(
        self,
        client: Client,
        auth_headers: Dict[str, Any],
        _incomplete_visits: list[Visit],
    ) -> None:
        """Each result contains the expected fields."""
        resp = client.get(self.URL, {"limit": 1}, **auth_headers)
        result = resp.json()["results"][0]
        assert "id" in result
        assert "patient_id" in result
        assert "status" in result
        assert "is_registration_missing" in result
        assert "is_departure_missing" in result
