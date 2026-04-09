"""Integration tests for the Patient CRUD endpoints."""

import pytest
from django.test import Client

from health_analytic_service.models import Patient


@pytest.fixture
def client():
    """Return a Django test client."""
    return Client()


class TestCreatePatient:
    """POST /api/v1/patients/"""

    def test_create_patient(self, client, auth_headers):
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

    def test_create_duplicate_patient(self, client, auth_headers, sample_patient):
        """Creating a patient with an existing patient_id returns 409 conflict."""
        resp = client.post(
            "/api/v1/patients/",
            data={"patient_id": sample_patient.patient_id},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 409


class TestListPatients:
    """GET /api/v1/patients/"""

    def test_list_empty(self, client, auth_headers, db):
        """An empty DB returns an empty list."""
        resp = client.get("/api/v1/patients/", **auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_with_patients(self, client, auth_headers, sample_patient):
        """Returns all patients."""
        resp = client.get("/api/v1/patients/", **auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["patient_id"] == "PAT-001"


class TestGetPatient:
    """GET /api/v1/patients/{patient_id}"""

    def test_get_existing(self, client, auth_headers, sample_patient):
        """Returns the patient by patient_id."""
        resp = client.get("/api/v1/patients/PAT-001", **auth_headers)
        assert resp.status_code == 200
        assert resp.json()["patient_id"] == "PAT-001"

    def test_get_not_found(self, client, auth_headers, db):
        """Returns 404 for an unknown patient_id."""
        resp = client.get("/api/v1/patients/NOPE", **auth_headers)
        assert resp.status_code == 404


class TestUpdatePatient:
    """PUT /api/v1/patients/{patient_id}"""

    def test_update_patient(self, client, auth_headers, sample_patient):
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

    def test_update_not_found(self, client, auth_headers, db):
        """Returns 404 for an unknown patient_id."""
        resp = client.put(
            "/api/v1/patients/NOPE",
            data={"patient_id": "NOPE"},
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 404


class TestDeletePatient:
    """DELETE /api/v1/patients/{patient_id}"""

    def test_delete_patient(self, client, auth_headers, sample_patient):
        """Deleting a patient removes it from the DB."""
        resp = client.delete("/api/v1/patients/PAT-001", **auth_headers)
        assert resp.status_code == 204
        assert not Patient.objects.filter(patient_id="PAT-001").exists()

    def test_delete_not_found(self, client, auth_headers, db):
        """Returns 404 for an unknown patient_id."""
        resp = client.delete("/api/v1/patients/NOPE", **auth_headers)
        assert resp.status_code == 404
