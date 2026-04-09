"""Shared test fixtures for the health_analytic_service test suite."""

from typing import Any, Dict

import pytest

from health_analytic_service.models import ApiKey, Patient


@pytest.fixture
def api_key(db: Any) -> ApiKey:
    """Create and return an active API key for authenticated test requests."""
    return ApiKey.objects.create(name="test-key", key="test-api-key-12345")


@pytest.fixture
def inactive_api_key(db: Any) -> ApiKey:
    """Create and return an *inactive* API key."""
    return ApiKey.objects.create(
        name="inactive-key",
        key="inactive-api-key-99999",
        is_active=False,
    )


@pytest.fixture
def auth_headers(api_key: ApiKey) -> Dict[str, Any]:
    """Return a dict with the X-API-Key header set to the active key.

    Django's test client expects headers as keyword arguments with the
    ``HTTP_`` prefix, e.g. ``HTTP_X_API_Key``.
    """
    return {"HTTP_X_API_Key": api_key.key}


@pytest.fixture
def sample_patient(db: Any) -> Patient:
    """Create and return a sample patient."""
    return Patient.objects.create(
        patient_id="PAT-001",
        patient_name="John Doe",
        date_of_birth="1990-01-15",
        ssn_last4="1234",
        contact_phone="555-0100",
    )


@pytest.fixture
def sample_record_payload() -> Dict[str, Any]:
    """Return a complete record ingest payload dict."""
    return {
        "record_id": "REC-001",
        "patient_id": "PAT-001",
        "patient_name": "John Doe",
        "date_of_birth": "1990-01-15",
        "ssn_last4": "1234",
        "contact_phone": "555-0100",
        "facility": "General Hospital",
        "timestamp": "2026-04-09T10:00:00Z",
        "event_type": "REGISTRATION",
        "acuity_level": 3,
        "chief_complaint": "Chest pain",
        "disposition": "ADMITTED",
        "diagnosis_codes": ["I21.0", "R07.9"],
    }
