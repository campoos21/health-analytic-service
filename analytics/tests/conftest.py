"""Shared fixtures for analytics tests."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest

from health_analytic_service.models import ApiKey, Patient, Record


@pytest.fixture
def api_key(db: Any) -> ApiKey:
    """Create and return an active API key."""
    return ApiKey.objects.create(name="analytics-test-key", key="analytics-key-12345")


@pytest.fixture
def auth_headers(api_key: ApiKey) -> Dict[str, Any]:
    """Return a dict with the X-API-Key header set."""
    return {"HTTP_X_API_Key": api_key.key}


# ── Time helpers ─────────────────────────────────────────────────────────────

BASE_TIME = datetime(2026, 4, 9, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def base_time() -> datetime:
    """Return a base UTC datetime for building event timelines."""
    return BASE_TIME


# ── Domain fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def patient(db: Any) -> Patient:
    """Create and return a sample patient."""
    return Patient.objects.create(patient_id="PAT-100", patient_name="Test Patient")


@pytest.fixture
def make_record(patient: Patient) -> Any:
    """Return a factory that creates a Record linked to the default patient."""
    _counter = 0

    def _make(event_type: str, minutes_offset: int = 0, **kwargs: Any) -> Record:
        nonlocal _counter
        _counter += 1
        return Record.objects.create(
            record_id=f"REC-{_counter:04d}",
            patient=kwargs.pop("patient", patient),
            timestamp=BASE_TIME + timedelta(minutes=minutes_offset),
            event_type=event_type,
            **kwargs,
        )

    return _make
