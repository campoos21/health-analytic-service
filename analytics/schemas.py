"""Pydantic schemas for analytics endpoints."""

from datetime import datetime
from typing import List, Optional

from ninja import Schema


# ─── Visit Duration (Endpoint 1) ────────────────────────────────────────────


class VisitDurationOut(Schema):
    """Single completed visit with computed duration."""

    id: int
    patient_id: str
    registration_at: datetime
    departure_at: datetime
    duration_seconds: int


class PaginatedDurationResponse(Schema):
    """Paginated list of completed-visit durations."""

    count: int
    results: List[VisitDurationOut]


# ─── Incomplete Visits (Endpoint 2) ─────────────────────────────────────────


class IncompleteVisitOut(Schema):
    """Single non-completed visit."""

    id: int
    patient_id: str
    status: str
    is_registration_missing: bool
    is_departure_missing: bool
    registration_at: Optional[datetime] = None


class PaginatedIncompleteResponse(Schema):
    """Paginated list of incomplete/in-progress visits."""

    count: int
    results: List[IncompleteVisitOut]
