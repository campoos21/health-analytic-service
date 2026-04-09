"""Integration tests for the Patient CRUD endpoints."""

from typing import Any, Dict

import pytest
from django.test import Client

from health_analytic_service.models import Patient


@pytest.fixture
def client() -> Client:
    """Return a Django test client."""
    return Client()


class TestCreatePatient:
    """POST /api/v1/patients/."""

    def test_create_patient(self, client: Client, auth_headers: Dict[str, Any]) -> None:
        """A valid payload creates a patient and returns 201."""
        resp = client.post(
            "/api/v1/patients/",
            data={"patient_id": "PAT-NEW", "patient_name": "Alice"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["patient_id"] == "PAT-NEW"
        assert body["patient_name"] == "Alice"
        assert Patient.objects.filter(patient_id="PAT-NEW").exists()

    def test_create_duplicate_patient(self, client: Client, auth_headers: Dict[str, Any], sample_patient: Any) -> None:
        """Creating a patient with an existing patient_id returns 409 conflict."""
        resp = client.post(
            "/api/v1/patients/",
            data={"patient_id": sample_patient.patient_id},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "A record with this identifier already exists."


class TestListPatients:
    """GET /api/v1/patients/."""

    def test_list_empty(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """An empty DB returns a paginated response with zero results."""
        resp = client.get("/api/v1/patients/", **auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["results"] == []

    def test_list_with_patients(self, client: Client, auth_headers: Dict[str, Any], sample_patient: Any) -> None:
        """Returns paginated patient summaries without PII."""
        resp = client.get("/api/v1/patients/", **auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert len(body["results"]) == 1
        result = body["results"][0]
        assert result["patient_id"] == "PAT-001"
        assert result["patient_name"] == "John Doe"
        # PII fields must NOT be present in summary
        assert "ssn_last4" not in result
        assert "contact_phone" not in result

    def test_list_pagination(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """Offset/limit pagination works correctly."""
        from health_analytic_service.models import Patient as PatientModel

        for i in range(5):
            PatientModel.objects.create(patient_id=f"PAT-PAGE-{i}")

        resp = client.get("/api/v1/patients/", {"offset": 0, "limit": 2}, **auth_headers)
        body = resp.json()
        assert body["count"] == 5
        assert len(body["results"]) == 2

        resp2 = client.get("/api/v1/patients/", {"offset": 4, "limit": 2}, **auth_headers)
        body2 = resp2.json()
        assert body2["count"] == 5
        assert len(body2["results"]) == 1


class TestGetPatient:
    """GET /api/v1/patients/{patient_id}."""

    def test_get_existing(self, client: Client, auth_headers: Dict[str, Any], sample_patient: Any) -> None:
        """Returns the patient by patient_id."""
        resp = client.get("/api/v1/patients/PAT-001", **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == "PAT-001"

    def test_get_not_found(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """Returns 404 for an unknown patient_id."""
        resp = client.get("/api/v1/patients/NOPE", **auth_headers)
        assert resp.status_code == 404


class TestUpdatePatient:
    """PUT /api/v1/patients/{patient_id}."""

    def test_update_patient(self, client: Client, auth_headers: Dict[str, Any], sample_patient: Any) -> None:
        """Updating a patient changes the fields."""
        resp = client.put(
            "/api/v1/patients/PAT-001",
            data={
                "patient_id": "PAT-001",
                "patient_name": "John Updated",
            },
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["patient_name"] == "John Updated"
        sample_patient.refresh_from_db()
        assert sample_patient.patient_name == "John Updated"

    def test_update_not_found(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """Returns 404 for an unknown patient_id."""
        resp = client.put(
            "/api/v1/patients/NOPE",
            data={"patient_id": "NOPE"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 404


class TestDeletePatient:
    """DELETE /api/v1/patients/{patient_id}."""

    def test_delete_patient(self, client: Client, auth_headers: Dict[str, Any], sample_patient: Any) -> None:
        """Deleting a patient removes it from the DB."""
        resp = client.delete("/api/v1/patients/PAT-001", **auth_headers)
        assert resp.status_code == 204
        assert not Patient.objects.filter(patient_id="PAT-001").exists()

    def test_delete_not_found(self, client: Client, auth_headers: Dict[str, Any], db: Any) -> None:
        """Returns 404 for an unknown patient_id."""
        resp = client.delete("/api/v1/patients/NOPE", **auth_headers)
        assert resp.status_code == 404
