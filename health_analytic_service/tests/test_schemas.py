"""Unit tests for Pydantic request/response schemas."""

from datetime import date
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from health_analytic_service.schemas import PatientIn, RecordIn


# ─── RecordIn ────────────────────────────────────────────────────────────────


class TestRecordInSchema:
    """Tests for the RecordIn schema."""

    def test_record_id_required(self) -> None:
        """Creating a RecordIn without record_id must raise ValidationError."""
        with pytest.raises(ValidationError):
            RecordIn()  # type: ignore[call-arg]

    def test_minimal_payload(self) -> None:
        """Only record_id is required; everything else defaults to None."""
        schema = RecordIn(record_id="REC-001")
        assert schema.record_id == "REC-001"
        assert schema.patient_id is None
        assert schema.facility is None
        assert schema.timestamp is None
        assert schema.event_type is None
        assert schema.acuity_level is None
        assert schema.chief_complaint is None
        assert schema.disposition is None
        assert schema.diagnosis_codes is None

    def test_full_payload(self, sample_record_payload: Dict[str, Any]) -> None:
        """A fully populated payload parses without error."""
        schema = RecordIn(**sample_record_payload)
        assert schema.record_id == "REC-001"
        assert schema.patient_id == "PAT-001"
        assert schema.acuity_level == 3
        assert schema.diagnosis_codes == ["I21.0", "R07.9"]

    def test_partial_payload(self) -> None:
        """A partial payload (record_id + some fields) parses correctly."""
        schema = RecordIn(
            record_id="REC-002",
            facility="Clinic A",
            event_type="TRIAGE",
        )
        assert schema.facility == "Clinic A"
        assert schema.patient_id is None


# ─── PatientIn ───────────────────────────────────────────────────────────────


class TestPatientInSchema:
    """Tests for the PatientIn schema."""

    def test_patient_id_required(self) -> None:
        """Creating a PatientIn without patient_id must raise ValidationError."""
        with pytest.raises(ValidationError):
            PatientIn()  # type: ignore[call-arg]

    def test_minimal_payload(self) -> None:
        """Only patient_id is required."""
        schema = PatientIn(patient_id="PAT-001")
        assert schema.patient_id == "PAT-001"
        assert schema.patient_name is None

    def test_full_payload(self) -> None:
        """All fields populated."""
        schema = PatientIn(
            patient_id="PAT-002",
            patient_name="Jane Doe",
            date_of_birth=date(1985, 6, 15),
            ssn_last4="5678",
            contact_phone="555-0200",
        )
        assert schema.patient_name == "Jane Doe"
        assert str(schema.date_of_birth) == "1985-06-15"
