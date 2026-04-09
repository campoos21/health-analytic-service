"""Visit assembly service.

Assigns incoming records to visits on every ingest.  The algorithm works as
follows:

1.  When a record with a ``patient`` and a ``timestamp`` is ingested, we look
    for an **open visit** (status ``IN_PROGRESS``) for that patient whose time
    window is compatible with the new event.

2.  *Compatible* means the gap between the new event's timestamp and the
    visit's current time boundaries is within ``VISIT_GAP_THRESHOLD_HOURS``
    (default 24 h).

3.  If a REGISTRATION event arrives, it **always** opens a new visit (unless
    one already exists that started with this exact record).

4.  If a DEPARTURE event arrives, it closes the visit it is attached to.

5.  If no compatible open visit is found, a new visit is created.  When that
    new visit's earliest event is not a REGISTRATION, we flag
    ``is_registration_missing = True``.

6.  After attaching, the per-stage timestamp field on the visit is updated and
    the missing-boundary flags are recomputed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from django.db import transaction

from analytics.models import Visit
from health_analytic_service.models import Patient, Record

if TYPE_CHECKING:
    from django.db.models import QuerySet

logger = logging.getLogger(__name__)

# Maps EventType values → Visit model field names.
_EVENT_TYPE_TO_FIELD: dict[str, str] = {
    Record.EventType.REGISTRATION: "registration_at",
    Record.EventType.TRIAGE: "triage_at",
    Record.EventType.BED_ASSIGNMENT: "bed_assignment_at",
    Record.EventType.TREATMENT: "treatment_at",
    Record.EventType.DISPOSITION: "disposition_at",
    Record.EventType.DEPARTURE: "departure_at",
}


def _gap_threshold() -> timedelta:
    """Return the configurable time-gap threshold as a ``timedelta``."""
    return timedelta(hours=getattr(settings, "VISIT_GAP_THRESHOLD_HOURS", 24))


def _is_within_gap(visit: Visit, timestamp: datetime, threshold: timedelta) -> bool:
    """Check whether *timestamp* falls within the visit's window ± threshold."""
    started = visit.started_at
    ended = visit.ended_at
    if started and ended:
        return bool((started - threshold) <= timestamp <= (ended + threshold))
    if started:
        return bool((started - threshold) <= timestamp <= (started + threshold))
    if ended:
        return bool((ended - threshold) <= timestamp <= (ended + threshold))
    # Visit has no timestamps yet – accept any event.
    return True


def _refresh_visit(visit: Visit, record: Record) -> None:
    """Update a visit's stage timestamp, flags, and status after a record is attached."""
    # Set the per-stage timestamp if the record has a known event type.
    event_type = record.event_type
    if event_type and event_type in _EVENT_TYPE_TO_FIELD:
        field = _EVENT_TYPE_TO_FIELD[event_type]
        setattr(visit, field, record.timestamp)

    # Recompute missing-boundary flags.
    visit.is_registration_missing = visit.registration_at is None
    visit.is_departure_missing = visit.departure_at is None

    # Update status.
    if visit.departure_at is not None:
        visit.status = Visit.Status.COMPLETED
    else:
        visit.status = Visit.Status.IN_PROGRESS

    visit.save()


def _find_open_visit(patient: Patient, timestamp: datetime, threshold: timedelta) -> Optional[Visit]:
    """Return the best open visit for *patient* that is time-compatible.

    The queryset uses ``select_for_update()`` to prevent concurrent
    modifications when called inside a ``transaction.atomic()`` block.
    """
    open_visits = Visit.objects.select_for_update().filter(
        patient=patient,
        status=Visit.Status.IN_PROGRESS,
    ).order_by("-registration_at")

    for visit in open_visits:
        if _is_within_gap(visit, timestamp, threshold):
            return visit
    return None


def assign_record_to_visit(record: Record) -> Optional[Visit]:
    """Assign *record* to a visit, creating one if needed.

    The entire operation runs inside ``transaction.atomic()`` with row-level
    locks (``select_for_update``) to prevent duplicate visits when records
    for the same patient are ingested concurrently.

    Returns the :class:`Visit` the record was attached to, or ``None`` if the
    record has no patient or timestamp (both are required to group visits).
    """
    if record.patient is None or record.timestamp is None:
        return None

    with transaction.atomic():
        threshold = _gap_threshold()
        patient = record.patient
        event_type = record.event_type

        # ── REGISTRATION always opens a new visit ────────────────────────
        if event_type == Record.EventType.REGISTRATION:
            # But first check if this record is already linked to a visit.
            if record.visit is not None:
                _refresh_visit(record.visit, record)
                return record.visit

            # Also check if there's already a visit that started with this exact
            # timestamp (idempotent re-send of REGISTRATION).
            existing = Visit.objects.select_for_update().filter(
                patient=patient,
                registration_at=record.timestamp,
            ).first()
            if existing is not None:
                record.visit = existing
                record.save(update_fields=["visit"])
                _refresh_visit(existing, record)
                logger.debug(
                    "Record %s re-attached to existing visit %s",
                    record.record_id, existing.pk,
                )
                return existing

            visit = Visit.objects.create(
                patient=patient,
                registration_at=record.timestamp,
                is_registration_missing=False,
            )
            record.visit = visit
            record.save(update_fields=["visit"])
            _refresh_visit(visit, record)
            logger.info(
                "Created visit %s for patient %s (REGISTRATION)",
                visit.pk, patient.patient_id,
            )
            return visit

        # ── Non-REGISTRATION events: attach to an existing open visit ────
        if record.visit is not None:
            # Already assigned – just refresh.
            _refresh_visit(record.visit, record)
            return record.visit

        found_visit = _find_open_visit(patient, record.timestamp, threshold)

        if found_visit is None:
            found_visit = Visit.objects.create(
                patient=patient,
                is_registration_missing=True,
            )
            logger.info(
                "Created visit %s for patient %s (missing registration)",
                found_visit.pk, patient.patient_id,
            )

        record.visit = found_visit
        record.save(update_fields=["visit"])
        _refresh_visit(found_visit, record)
        return found_visit


# ─── Analytical query helpers ────────────────────────────────────────────────


def get_completed_visit_durations(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> "QuerySet[Visit]":
    """Return completed visits annotated with ``duration``.

    Only visits that have both ``registration_at`` and ``departure_at`` set
    (i.e. ``status=COMPLETED``) are included.  An optional date-range filter
    is applied on ``registration_at``.

    The returned queryset is annotated with a ``duration`` field (a
    ``timedelta``) computed as ``departure_at − registration_at``.
    """
    from django.db.models import F  # local to avoid top-level circular risk

    qs = Visit.objects.filter(
        status=Visit.Status.COMPLETED,
        registration_at__isnull=False,
        departure_at__isnull=False,
    )

    if date_from is not None:
        qs = qs.filter(registration_at__gte=date_from)
    if date_to is not None:
        qs = qs.filter(registration_at__lte=date_to)

    return qs.annotate(duration=F("departure_at") - F("registration_at")).order_by(
        "-registration_at"
    )


def get_incomplete_visits(
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> "QuerySet[Visit]":
    """Return visits that are **not** completed.

    This includes ``IN_PROGRESS`` visits (still open) and ``INCOMPLETE``
    visits (closed but missing boundary events).  An optional date-range
    filter is applied on ``registration_at``.
    """
    qs = Visit.objects.filter(
        status__in=[Visit.Status.IN_PROGRESS, Visit.Status.INCOMPLETE],
    )

    if date_from is not None:
        qs = qs.filter(registration_at__gte=date_from)
    if date_to is not None:
        qs = qs.filter(registration_at__lte=date_to)

    return qs.order_by("-created_at")
