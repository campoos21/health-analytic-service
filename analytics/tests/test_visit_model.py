"""Tests for the Visit model."""

from datetime import datetime, timezone
from typing import Any

import pytest

from analytics.models import Visit


pytestmark = pytest.mark.django_db


class TestVisitModel:
    """Basic Visit model behaviour."""

    def test_create_visit(self, patient: Any) -> None:
        """A visit can be created with just a patient."""
        visit = Visit.objects.create(patient=patient)
        assert visit.pk is not None
        assert visit.status == Visit.Status.IN_PROGRESS
        assert visit.is_registration_missing is False
        assert visit.is_departure_missing is False

    def test_str_representation(self, patient: Any) -> None:
        """__str__ includes pk, patient, and status."""
        visit = Visit.objects.create(patient=patient)
        result = str(visit)
        assert f"Visit {visit.pk}" in result
        assert str(patient) in result
        assert "IN_PROGRESS" in result

    def test_cascade_delete_patient(self, patient: Any) -> None:
        """Deleting a patient cascades to its visits."""
        Visit.objects.create(patient=patient)
        assert Visit.objects.count() == 1
        patient.delete()
        assert Visit.objects.count() == 0

    def test_ordering_by_registration_at(self, patient: Any) -> None:
        """Visits are ordered by -registration_at."""
        t1 = datetime(2026, 4, 9, 8, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 4, 9, 10, 0, tzinfo=timezone.utc)
        v1 = Visit.objects.create(patient=patient, registration_at=t1)
        v2 = Visit.objects.create(patient=patient, registration_at=t2)
        visits = list(Visit.objects.all())
        assert visits[0] == v2
        assert visits[1] == v1


class TestVisitStartedAtEndedAt:
    """Tests for the started_at / ended_at computed properties."""

    def test_started_at_returns_earliest(self, patient: Any) -> None:
        """started_at returns the minimum of all stage timestamps."""
        visit = Visit.objects.create(
            patient=patient,
            registration_at=datetime(2026, 4, 9, 8, 0, tzinfo=timezone.utc),
            triage_at=datetime(2026, 4, 9, 8, 15, tzinfo=timezone.utc),
            departure_at=datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
        )
        assert visit.started_at == datetime(2026, 4, 9, 8, 0, tzinfo=timezone.utc)

    def test_ended_at_returns_latest(self, patient: Any) -> None:
        """ended_at returns the maximum of all stage timestamps."""
        visit = Visit.objects.create(
            patient=patient,
            registration_at=datetime(2026, 4, 9, 8, 0, tzinfo=timezone.utc),
            departure_at=datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc),
        )
        assert visit.ended_at == datetime(2026, 4, 9, 12, 0, tzinfo=timezone.utc)

    def test_started_at_none_when_no_timestamps(self, patient: Any) -> None:
        """started_at is None when no stage timestamps are set."""
        visit = Visit.objects.create(patient=patient)
        assert visit.started_at is None

    def test_ended_at_none_when_no_timestamps(self, patient: Any) -> None:
        """ended_at is None when no stage timestamps are set."""
        visit = Visit.objects.create(patient=patient)
        assert visit.ended_at is None

    def test_single_timestamp_is_both_start_and_end(self, patient: Any) -> None:
        """When only one stage is set, started_at == ended_at."""
        t = datetime(2026, 4, 9, 9, 0, tzinfo=timezone.utc)
        visit = Visit.objects.create(patient=patient, triage_at=t)
        assert visit.started_at == t
        assert visit.ended_at == t

    def test_ignores_none_timestamps(self, patient: Any) -> None:
        """Only non-None timestamps contribute to started_at / ended_at."""
        visit = Visit.objects.create(
            patient=patient,
            registration_at=None,
            triage_at=datetime(2026, 4, 9, 8, 30, tzinfo=timezone.utc),
            treatment_at=datetime(2026, 4, 9, 9, 30, tzinfo=timezone.utc),
            departure_at=None,
        )
        assert visit.started_at == datetime(2026, 4, 9, 8, 30, tzinfo=timezone.utc)
        assert visit.ended_at == datetime(2026, 4, 9, 9, 30, tzinfo=timezone.utc)
