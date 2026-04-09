"""Integration tests for the Record ingest endpoint."""

from typing import Any, Dict

import pytest
from django.test import Client

from health_analytic_service.models import Patient, Record


@pytest.fixture
def client() -> Client:
    """Return a Django test client."""
    return Client()


class TestRecordIngest:
    """POST /api/v1/records/."""

    def test_create_record_full_payload(
        self, client: Client, auth_headers: Dict[str, Any], sample_record_payload: Dict[str, Any],
    ) -> None:
        """A full payload creates a record and its patient, returns 201."""
        resp = client.post(
            "/api/v1/records/",
            data=sample_record_payload,
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["record_id"] == "REC-001"
        assert body["created"] is True
        assert body["patient_id"] == "PAT-001"
        assert body["facility"] == "General Hospital"
        assert Record.objects.filter(record_id="REC-001").exists()
        assert Patient.objects.filter(patient_id="PAT-001").exists()

    def test_create_record_minimal(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """Only record_id is required — a minimal payload succeeds."""
        resp = client.post(
            "/api/v1/records/",
            data={"record_id": "REC-MIN"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["record_id"] == "REC-MIN"
        assert body["patient_id"] is None
        assert body["facility"] is None

    def test_missing_record_id(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """A payload without record_id returns 422."""
        resp = client.post(
            "/api/v1/records/",
            data={"facility": "Clinic"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 422

    def test_upsert_same_record_id(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """Sending the same record_id twice updates instead of duplicating."""
        # First send
        resp1 = client.post(
            "/api/v1/records/",
            data={"record_id": "REC-UPS", "facility": "Hospital A"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp1.status_code == 201
        assert resp1.json()["created"] is True

        # Second send with updated facility
        resp2 = client.post(
            "/api/v1/records/",
            data={"record_id": "REC-UPS", "facility": "Hospital B"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp2.status_code == 200
        assert resp2.json()["created"] is False
        assert resp2.json()["facility"] == "Hospital B"

        # Only one record in DB
        assert Record.objects.filter(record_id="REC-UPS").count() == 1

    def test_partial_upsert_preserves_fields(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """A partial re-send does NOT erase previously ingested fields."""
        # Full initial send
        client.post(
            "/api/v1/records/",
            data={
                "record_id": "REC-PARTIAL",
                "facility": "Hospital A",
                "chief_complaint": "Headache",
            },
            content_type="application/json",
            **auth_headers,
        )

        # Partial re-send — only updates event_type
        resp = client.post(
            "/api/v1/records/",
            data={"record_id": "REC-PARTIAL", "event_type": "TRIAGE"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        # New field applied
        assert body["event_type"] == "TRIAGE"
        # Old fields preserved
        assert body["facility"] == "Hospital A"
        assert body["chief_complaint"] == "Headache"

    def test_patient_get_or_create(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """When patient_id is supplied, the patient is get-or-created."""
        payload1 = {
            "record_id": "REC-P1",
            "patient_id": "PAT-GOC",
            "patient_name": "Original Name",
        }
        payload2 = {
            "record_id": "REC-P2",
            "patient_id": "PAT-GOC",
            "patient_name": "Updated Name",
        }

        client.post(
            "/api/v1/records/",
            data=payload1,
            content_type="application/json",
            **auth_headers,
        )
        client.post(
            "/api/v1/records/",
            data=payload2,
            content_type="application/json",
            **auth_headers,
        )

        # Only one patient created
        assert Patient.objects.filter(patient_id="PAT-GOC").count() == 1
        # Patient name was updated by the second call
        patient = Patient.objects.get(patient_id="PAT-GOC")
        assert patient.patient_name == "Updated Name"

    def test_record_without_patient(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """A record with no patient_id still succeeds."""
        resp = client.post(
            "/api/v1/records/",
            data={"record_id": "REC-NOPAT", "facility": "Walk-in"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["patient_id"] is None
