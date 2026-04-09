"""Tests for the visit assembly service (analytics.services)."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest
from django.test import Client, override_settings

from analytics.models import Visit
from analytics.services import assign_record_to_visit
from health_analytic_service.models import Patient, Record


BASE_TIME = datetime(2026, 4, 9, 8, 0, 0, tzinfo=timezone.utc)


pytestmark = pytest.mark.django_db


# ─── Happy path: full visit lifecycle ────────────────────────────────────────


class TestFullVisitLifecycle:
    """Events arrive in order: REGISTRATION → … → DEPARTURE."""

    def test_registration_creates_visit(self, make_record: Any) -> None:
        """A REGISTRATION event creates a new visit."""
        rec = make_record("REGISTRATION", minutes_offset=0)
        visit = assign_record_to_visit(rec)

        assert visit is not None
        assert visit.status == Visit.Status.IN_PROGRESS
        assert visit.registration_at == rec.timestamp
        assert visit.is_registration_missing is False
        assert visit.is_departure_missing is True
        assert rec.visit == visit

    def test_subsequent_events_attach_to_same_visit(self, make_record: Any) -> None:
        """TRIAGE, BED_ASSIGNMENT, TREATMENT attach to the open visit."""
        reg = make_record("REGISTRATION", minutes_offset=0)
        v = assign_record_to_visit(reg)

        tri = make_record("TRIAGE", minutes_offset=15)
        assert assign_record_to_visit(tri) == v

        bed = make_record("BED_ASSIGNMENT", minutes_offset=30)
        assert assign_record_to_visit(bed) == v

        treat = make_record("TREATMENT", minutes_offset=60)
        assert assign_record_to_visit(treat) == v

        assert v is not None
        v.refresh_from_db()
        assert v.triage_at == tri.timestamp
        assert v.bed_assignment_at == bed.timestamp
        assert v.treatment_at == treat.timestamp
        assert v.status == Visit.Status.IN_PROGRESS

    def test_departure_completes_visit(self, make_record: Any) -> None:
        """A DEPARTURE event sets the visit to COMPLETED."""
        reg = make_record("REGISTRATION", minutes_offset=0)
        v = assign_record_to_visit(reg)

        dep = make_record("DEPARTURE", minutes_offset=120)
        assign_record_to_visit(dep)

        assert v is not None
        v.refresh_from_db()
        assert v.status == Visit.Status.COMPLETED
        assert v.departure_at == dep.timestamp
        assert v.is_departure_missing is False

    def test_all_stage_timestamps_populated(self, make_record: Any) -> None:
        """After a full flow, all six stage timestamps are set on the visit."""
        events = [
            ("REGISTRATION", 0),
            ("TRIAGE", 10),
            ("BED_ASSIGNMENT", 25),
            ("TREATMENT", 40),
            ("DISPOSITION", 90),
            ("DEPARTURE", 120),
        ]
        visit = None
        for event_type, offset in events:
            rec = make_record(event_type, minutes_offset=offset)
            visit = assign_record_to_visit(rec)

        assert visit is not None
        visit.refresh_from_db()
        assert visit.registration_at is not None
        assert visit.triage_at is not None
        assert visit.bed_assignment_at is not None
        assert visit.treatment_at is not None
        assert visit.disposition_at is not None
        assert visit.departure_at is not None
        assert visit.status == Visit.Status.COMPLETED
        assert visit.is_registration_missing is False
        assert visit.is_departure_missing is False


# ─── Missing REGISTRATION ───────────────────────────────────────────────────


class TestMissingRegistration:
    """Events arrive without a REGISTRATION event."""

    def test_non_registration_creates_visit_with_flag(self, make_record: Any) -> None:
        """A TRIAGE without prior REGISTRATION creates a visit flagged as missing."""
        rec = make_record("TRIAGE", minutes_offset=10)
        visit = assign_record_to_visit(rec)

        assert visit is not None
        assert visit.is_registration_missing is True
        assert visit.triage_at == rec.timestamp
        assert visit.registration_at is None

    def test_subsequent_events_still_group(self, make_record: Any) -> None:
        """Further events attach to the same visit even without REGISTRATION."""
        tri = make_record("TRIAGE", minutes_offset=10)
        v = assign_record_to_visit(tri)

        treat = make_record("TREATMENT", minutes_offset=40)
        assert assign_record_to_visit(treat) == v

        dep = make_record("DEPARTURE", minutes_offset=120)
        assign_record_to_visit(dep)

        assert v is not None
        v.refresh_from_db()
        assert v.is_registration_missing is True
        assert v.is_departure_missing is False
        assert v.status == Visit.Status.COMPLETED


# ─── Missing DEPARTURE ──────────────────────────────────────────────────────


class TestMissingDeparture:
    """Visit has REGISTRATION but no DEPARTURE arrives."""

    def test_visit_stays_in_progress(self, make_record: Any) -> None:
        """Without DEPARTURE the visit remains IN_PROGRESS."""
        reg = make_record("REGISTRATION", minutes_offset=0)
        v = assign_record_to_visit(reg)

        make_record("TRIAGE", minutes_offset=15)
        assign_record_to_visit(make_record("TREATMENT", minutes_offset=60))

        assert v is not None
        v.refresh_from_db()
        assert v.status == Visit.Status.IN_PROGRESS
        assert v.is_departure_missing is True
        assert v.departure_at is None


# ─── Multiple visits for one patient ────────────────────────────────────────


class TestMultipleVisits:
    """Same patient has distinct visits separated by time."""

    def test_second_registration_creates_new_visit(self, make_record: Any) -> None:
        """A second REGISTRATION always creates a new visit."""
        reg1 = make_record("REGISTRATION", minutes_offset=0)
        v1 = assign_record_to_visit(reg1)

        dep1 = make_record("DEPARTURE", minutes_offset=120)
        assign_record_to_visit(dep1)

        # Second visit starts 2 days later
        reg2 = make_record("REGISTRATION", minutes_offset=60 * 48)
        v2 = assign_record_to_visit(reg2)

        assert v1 is not None
        assert v2 is not None
        assert v1.pk != v2.pk
        assert Visit.objects.count() == 2

    def test_time_gap_splits_visits(self, make_record: Any) -> None:
        """Events beyond the gap threshold go to a new visit."""
        tri1 = make_record("TRIAGE", minutes_offset=0)
        v1 = assign_record_to_visit(tri1)

        # 30 hours later — beyond 24h threshold
        tri2 = make_record("TRIAGE", minutes_offset=60 * 30)
        v2 = assign_record_to_visit(tri2)

        assert v1 is not None
        assert v2 is not None
        assert v1.pk != v2.pk
        assert v1.is_registration_missing is True
        assert v2.is_registration_missing is True

    @override_settings(VISIT_GAP_THRESHOLD_HOURS=2)
    def test_custom_gap_threshold(self, make_record: Any) -> None:
        """The VISIT_GAP_THRESHOLD_HOURS setting controls the split window."""
        tri1 = make_record("TRIAGE", minutes_offset=0)
        v1 = assign_record_to_visit(tri1)

        # 3 hours later — beyond the 2h custom threshold
        tri2 = make_record("TRIAGE", minutes_offset=180)
        v2 = assign_record_to_visit(tri2)

        assert v1 is not None
        assert v2 is not None
        assert v1.pk != v2.pk

    @override_settings(VISIT_GAP_THRESHOLD_HOURS=2)
    def test_within_custom_gap_stays_same_visit(self, make_record: Any) -> None:
        """Events within the custom threshold stay in the same visit."""
        tri1 = make_record("TRIAGE", minutes_offset=0)
        v1 = assign_record_to_visit(tri1)

        # 1 hour later — within the 2h custom threshold
        treat = make_record("TREATMENT", minutes_offset=60)
        v2 = assign_record_to_visit(treat)

        assert v1 is not None
        assert v2 is not None
        assert v1.pk == v2.pk


# ─── Idempotency ────────────────────────────────────────────────────────────


class TestIdempotency:
    """Re-processing the same record should not create duplicates."""

    def test_reprocess_registration(self, make_record: Any) -> None:
        """Calling assign twice on the same REGISTRATION doesn't duplicate."""
        rec = make_record("REGISTRATION", minutes_offset=0)
        v1 = assign_record_to_visit(rec)
        v2 = assign_record_to_visit(rec)

        assert v1 is not None
        assert v2 is not None
        assert v1.pk == v2.pk
        assert Visit.objects.count() == 1

    def test_reprocess_non_registration(self, make_record: Any) -> None:
        """Calling assign twice on a TRIAGE doesn't duplicate."""
        reg = make_record("REGISTRATION", minutes_offset=0)
        assign_record_to_visit(reg)

        tri = make_record("TRIAGE", minutes_offset=15)
        v1 = assign_record_to_visit(tri)
        v2 = assign_record_to_visit(tri)

        assert v1 is not None
        assert v2 is not None
        assert v1.pk == v2.pk
        assert Visit.objects.count() == 1

    def test_duplicate_registration_same_timestamp(self, make_record: Any, patient: Any) -> None:
        """Two REGISTRATION records with the same timestamp reuse the visit."""
        rec1 = Record.objects.create(
            record_id="REC-DUP-1",
            patient=patient,
            timestamp=BASE_TIME,
            event_type="REGISTRATION",
        )
        rec2 = Record.objects.create(
            record_id="REC-DUP-2",
            patient=patient,
            timestamp=BASE_TIME,
            event_type="REGISTRATION",
        )
        v1 = assign_record_to_visit(rec1)
        v2 = assign_record_to_visit(rec2)

        assert v1 is not None
        assert v2 is not None
        assert v1.pk == v2.pk
        assert Visit.objects.count() == 1


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases: records without patient, timestamp, or event_type."""

    def test_no_patient_returns_none(self, db: Any) -> None:
        """A record without a patient is not assigned to any visit."""
        rec = Record.objects.create(
            record_id="REC-NOPAT",
            timestamp=BASE_TIME,
            event_type="REGISTRATION",
        )
        assert assign_record_to_visit(rec) is None
        assert Visit.objects.count() == 0

    def test_no_timestamp_returns_none(self, patient: Any) -> None:
        """A record without a timestamp is not assigned to any visit."""
        rec = Record.objects.create(
            record_id="REC-NOTS",
            patient=patient,
            event_type="REGISTRATION",
        )
        assert assign_record_to_visit(rec) is None
        assert Visit.objects.count() == 0

    def test_no_event_type_still_assigns(self, make_record: Any) -> None:
        """A record with no event_type is attached but no stage timestamp is set."""
        reg = make_record("REGISTRATION", minutes_offset=0)
        v = assign_record_to_visit(reg)

        rec = Record.objects.create(
            record_id="REC-NOET",
            patient=reg.patient,
            timestamp=BASE_TIME + timedelta(minutes=20),
        )
        assert assign_record_to_visit(rec) == v
        assert v is not None
        v.refresh_from_db()
        # No extra stage timestamp should have been touched
        assert v.triage_at is None

    def test_different_patients_separate_visits(self, db: Any, make_record: Any) -> None:
        """Events for different patients go to different visits."""
        pat_a = Patient.objects.create(patient_id="PAT-A")
        pat_b = Patient.objects.create(patient_id="PAT-B")

        rec_a = Record.objects.create(
            record_id="REC-A1",
            patient=pat_a,
            timestamp=BASE_TIME,
            event_type="REGISTRATION",
        )
        rec_b = Record.objects.create(
            record_id="REC-B1",
            patient=pat_b,
            timestamp=BASE_TIME,
            event_type="REGISTRATION",
        )
        v_a = assign_record_to_visit(rec_a)
        v_b = assign_record_to_visit(rec_b)

        assert v_a is not None
        assert v_b is not None
        assert v_a.pk != v_b.pk
        assert v_a.patient == pat_a
        assert v_b.patient == pat_b


# ─── Integration: ingest endpoint triggers visit assembly ────────────────────


class TestIngestCreatesVisit:
    """POST /api/v1/records/ triggers visit assembly."""

    @pytest.fixture
    def client(self) -> Client:
        """Return a Django test client."""
        from django.test import Client
        return Client()

    def test_ingest_registration_creates_visit(self, client: Any, auth_headers: Dict[str, Any], db: Any) -> None:
        """Ingesting a REGISTRATION via the API creates a Visit."""
        resp = client.post(
            "/api/v1/records/",
            data={
                "record_id": "REC-INT-1",
                "patient_id": "PAT-INT",
                "timestamp": "2026-04-09T08:00:00Z",
                "event_type": "REGISTRATION",
            },
            content_type="application/json",
            **auth_headers,
        )
        assert resp.status_code == 201
        assert Visit.objects.count() == 1
        visit = Visit.objects.first()
        assert visit is not None
        assert visit.registration_at is not None
        assert visit.is_registration_missing is False

    def test_ingest_full_flow_creates_completed_visit(self, client: Any, auth_headers: Dict[str, Any], db: Any) -> None:
        """Ingesting a full event sequence via the API produces a COMPLETED visit."""
        events = [
            ("REC-FLOW-1", "REGISTRATION", "2026-04-09T08:00:00Z"),
            ("REC-FLOW-2", "TRIAGE", "2026-04-09T08:15:00Z"),
            ("REC-FLOW-3", "TREATMENT", "2026-04-09T08:45:00Z"),
            ("REC-FLOW-4", "DEPARTURE", "2026-04-09T10:00:00Z"),
        ]
        for rec_id, event_type, ts in events:
            client.post(
                "/api/v1/records/",
                data={
                    "record_id": rec_id,
                    "patient_id": "PAT-FLOW",
                    "timestamp": ts,
                    "event_type": event_type,
                },
                content_type="application/json",
                **auth_headers,
            )

        assert Visit.objects.count() == 1
        visit = Visit.objects.first()
        assert visit is not None
        assert visit.status == Visit.Status.COMPLETED
        assert visit.is_registration_missing is False
        assert visit.is_departure_missing is False

    def test_ingest_without_patient_no_visit(self, client: Any, auth_headers: Dict[str, Any], db: Any) -> None:
        """A record without patient_id does not create a visit."""
        client.post(
            "/api/v1/records/",
            data={
                "record_id": "REC-NOPAT",
                "timestamp": "2026-04-09T08:00:00Z",
                "event_type": "REGISTRATION",
            },
            content_type="application/json",
            **auth_headers,
        )
        assert Visit.objects.count() == 0

    def test_ingest_without_timestamp_no_visit(self, client: Any, auth_headers: Dict[str, Any], db: Any) -> None:
        """A record without timestamp does not create a visit."""
        client.post(
            "/api/v1/records/",
            data={
                "record_id": "REC-NOTS",
                "patient_id": "PAT-NOTS",
                "event_type": "REGISTRATION",
            },
            content_type="application/json",
            **auth_headers,
        )
        assert Visit.objects.count() == 0
