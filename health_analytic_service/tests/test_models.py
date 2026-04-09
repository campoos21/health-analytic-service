"""Unit tests for the core domain models."""

from datetime import date
from typing import Any

import pytest
from django.db import IntegrityError

from health_analytic_service.models import ApiKey, Patient, Record, generate_api_key


# ─── ApiKey ──────────────────────────────────────────────────────────────────


class TestApiKeyModel:
    """Tests for the ApiKey model."""

    def test_create_api_key(self, db: Any) -> None:
        """An ApiKey can be created with just a name."""
        key = ApiKey.objects.create(name="service-a")
        assert key.pk is not None
        assert key.is_active is True
        assert len(key.key) == 40  # secrets.token_hex(20) → 40 chars

    def test_api_key_unique(self, db: Any) -> None:
        """Duplicate key values must be rejected."""
        ApiKey.objects.create(name="a", key="same-key")
        with pytest.raises(IntegrityError):
            ApiKey.objects.create(name="b", key="same-key")

    def test_generate_api_key_returns_hex(self) -> None:
        """generate_api_key must return a 40-char hex string."""
        k = generate_api_key()
        assert len(k) == 40
        int(k, 16)  # raises ValueError if not valid hex

    def test_str_representation(self, db: Any) -> None:
        """__str__ includes the name and a masked key preview."""
        key = ApiKey.objects.create(name="my-key", key="abcdef1234567890aabb")
        assert "my-key" in str(key)
        assert "abcdef12" in str(key)


# ─── Patient ─────────────────────────────────────────────────────────────────


class TestPatientModel:
    """Tests for the Patient model."""

    def test_create_patient_minimal(self, db: Any) -> None:
        """A patient can be created with only patient_id."""
        p = Patient.objects.create(patient_id="PAT-100")
        assert p.pk is not None
        assert p.patient_name is None
        assert p.date_of_birth is None
        assert p.ssn_last4 is None
        assert p.contact_phone is None

    def test_create_patient_full(self, db: Any) -> None:
        """A patient can be created with all fields populated."""
        p = Patient.objects.create(
            patient_id="PAT-200",
            patient_name="Jane Doe",
            date_of_birth=date(1985, 6, 15),
            ssn_last4="5678",
            contact_phone="555-0200",
        )
        assert p.patient_name == "Jane Doe"
        assert p.date_of_birth == date(1985, 6, 15)

    def test_patient_id_unique(self, db: Any) -> None:
        """Duplicate patient_id values must be rejected."""
        Patient.objects.create(patient_id="PAT-DUP")
        with pytest.raises(IntegrityError):
            Patient.objects.create(patient_id="PAT-DUP")

    def test_str_representation(self, db: Any) -> None:
        """__str__ includes the patient_id."""
        p = Patient.objects.create(patient_id="PAT-STR")
        assert "PAT-STR" in str(p)


# ─── Record ──────────────────────────────────────────────────────────────────


class TestRecordModel:
    """Tests for the Record model."""

    def test_create_record_minimal(self, db: Any) -> None:
        """A record can be created with only record_id."""
        r = Record.objects.create(record_id="REC-100")
        assert r.pk is not None
        assert r.patient is None
        assert r.facility is None
        assert r.timestamp is None
        assert r.event_type is None
        assert r.acuity_level is None
        assert r.chief_complaint is None
        assert r.disposition is None
        assert r.diagnosis_codes == []

    def test_create_record_full(self, sample_patient: Patient) -> None:
        """A record can be created with all fields populated."""
        r = Record.objects.create(
            record_id="REC-200",
            patient=sample_patient,
            facility="General Hospital",
            timestamp="2026-04-09T10:00:00Z",
            event_type=Record.EventType.REGISTRATION,
            acuity_level=3,
            chief_complaint="Chest pain",
            disposition=Record.DispositionChoice.ADMITTED,
            diagnosis_codes=["I21.0"],
        )
        assert r.patient == sample_patient
        assert r.event_type == "REGISTRATION"

    def test_record_id_unique(self, db: Any) -> None:
        """Duplicate record_id values must be rejected."""
        Record.objects.create(record_id="REC-DUP")
        with pytest.raises(IntegrityError):
            Record.objects.create(record_id="REC-DUP")

    def test_fk_set_null_on_patient_delete(self, sample_patient: Patient) -> None:
        """Deleting a patient sets record.patient to NULL (not cascade)."""
        r = Record.objects.create(record_id="REC-FK", patient=sample_patient)
        sample_patient.delete()
        r.refresh_from_db()
        assert r.patient is None

    def test_str_representation(self, db: Any) -> None:
        """__str__ includes the record_id."""
        r = Record.objects.create(record_id="REC-STR")
        assert "REC-STR" in str(r)
