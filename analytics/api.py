"""Analytical endpoints – visit durations & incomplete visits.

Both endpoints:
* inherit global ``ApiKeyAuth`` + ``AuthRateThrottle`` from the NinjaAPI instance
* support optional ``date_from`` / ``date_to`` filtering on ``registration_at``
* support offset / limit pagination
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from django.http import HttpRequest
from ninja import Query, Router

from analytics.schemas import (
    IncompleteVisitOut,
    PaginatedDurationResponse,
    PaginatedIncompleteResponse,
    VisitDurationOut,
)
from analytics.services import get_completed_visit_durations, get_incomplete_visits

router = Router(tags=["analytics"])

# ─── Defaults ────────────────────────────────────────────────────────────────

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


# ─── Endpoint 1 – Visit durations ───────────────────────────────────────────


@router.get("/visit-durations", response=PaginatedDurationResponse)
def visit_durations(
    request: HttpRequest,
    date_from: Optional[datetime] = Query(None),  # type: ignore[type-arg]  # noqa: B008
    date_to: Optional[datetime] = Query(None),  # type: ignore[type-arg]  # noqa: B008
    offset: int = Query(0),  # type: ignore[type-arg]  # noqa: B008
    limit: int = Query(_DEFAULT_LIMIT),  # type: ignore[type-arg]  # noqa: B008
) -> PaginatedDurationResponse:
    """Return the duration (in seconds) of every completed visit.

    A completed visit has both ``registration_at`` and ``departure_at``.
    The duration is ``departure_at − registration_at`` expressed as an
    integer number of seconds.
    """
    limit = min(limit, _MAX_LIMIT)
    qs = get_completed_visit_durations(date_from=date_from, date_to=date_to)
    count = qs.count()
    page = qs[offset:offset + limit]

    results: list[VisitDurationOut] = []
    for v in page.select_related("patient"):
        duration: timedelta = getattr(v, "duration")  # annotation from F()
        results.append(
            VisitDurationOut(
                id=v.pk,
                patient_id=v.patient.patient_id,
                registration_at=v.registration_at,  # type: ignore[arg-type]
                departure_at=v.departure_at,  # type: ignore[arg-type]
                duration_seconds=int(duration.total_seconds()),
            )
        )

    return PaginatedDurationResponse(count=count, results=results)


# ─── Endpoint 2 – Incomplete / in-progress visits ───────────────────────────


@router.get("/incomplete-visits", response=PaginatedIncompleteResponse)
def incomplete_visits(
    request: HttpRequest,
    date_from: Optional[datetime] = Query(None),  # type: ignore[type-arg]  # noqa: B008
    date_to: Optional[datetime] = Query(None),  # type: ignore[type-arg]  # noqa: B008
    offset: int = Query(0),  # type: ignore[type-arg]  # noqa: B008
    limit: int = Query(_DEFAULT_LIMIT),  # type: ignore[type-arg]  # noqa: B008
) -> PaginatedIncompleteResponse:
    """Return visits that have **not** been completed.

    Includes ``IN_PROGRESS`` (still open) and ``INCOMPLETE`` (closed but
    missing boundary events such as REGISTRATION or DEPARTURE).
    """
    limit = min(limit, _MAX_LIMIT)
    qs = get_incomplete_visits(date_from=date_from, date_to=date_to)
    count = qs.count()
    page = qs[offset:offset + limit]

    results: list[IncompleteVisitOut] = []
    for v in page.select_related("patient"):
        results.append(
            IncompleteVisitOut(
                id=v.pk,
                patient_id=v.patient.patient_id,
                status=v.status,
                is_registration_missing=v.is_registration_missing,
                is_departure_missing=v.is_departure_missing,
                registration_at=v.registration_at,
            )
        )

    return PaginatedIncompleteResponse(count=count, results=results)
