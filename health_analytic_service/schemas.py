"""Pydantic schemas for request/response validation."""

from datetime import date, datetime
from typing import List, Optional

from ninja import Schema


# ─── Auth ────────────────────────────────────────────────────────────────────


class MessageOut(Schema):
    """Generic message response."""

    message: str


# ─── Patient Schemas ─────────────────────────────────────────────────────────


class PatientIn(Schema):
    """Schema for creating / updating a patient."""

    patient_id: str
    patient_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    ssn_last4: Optional[str] = None
    contact_phone: Optional[str] = None


class PatientOut(Schema):
    """Schema returned when reading a patient."""

    id: int
    patient_id: str
    patient_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    ssn_last4: Optional[str] = None
    contact_phone: Optional[str] = None


# ─── Record Schemas ──────────────────────────────────────────────────────────


class RecordIn(Schema):
    """Schema for ingesting an ED visit record.

    Only ``record_id`` is required. Everything else is optional so that
    partial payloads, duplicate sends, and out-of-order records are accepted.
    """

    record_id: str
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    ssn_last4: Optional[str] = None
    contact_phone: Optional[str] = None
    facility: Optional[str] = None
    timestamp: Optional[datetime] = None
    event_type: Optional[str] = None
    acuity_level: Optional[int] = None
    chief_complaint: Optional[str] = None
    disposition: Optional[str] = None
    diagnosis_codes: Optional[List[str]] = None


class RecordOut(Schema):
    """Schema returned after a record upsert."""

    id: int
    record_id: str
    patient_id: Optional[str] = None
    facility: Optional[str] = None
    timestamp: Optional[datetime] = None
    event_type: Optional[str] = None
    acuity_level: Optional[int] = None
    chief_complaint: Optional[str] = None
    disposition: Optional[str] = None
    diagnosis_codes: Optional[List[str]] = None
    created: bool  # True if the record was newly created, False if updated
