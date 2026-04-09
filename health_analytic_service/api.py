"""Main Django Ninja API – v1.

Includes:
* Patient CRUD router   → ``/api/v1/patients/``
* Record ingest endpoint → ``/api/v1/records/``
* Analytics router       → ``/api/v1/analytics/``
"""

import logging
from typing import Any, List, Tuple

from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import NinjaAPI, Query, Router
from ninja.throttling import AuthRateThrottle

from analytics.services import assign_record_to_visit
from health_analytic_service.auth import ApiKeyAuth
from health_analytic_service.models import Patient, Record
from health_analytic_service.schemas import (
    PaginatedPatientResponse,
    PatientIn,
    PatientOut,
    PatientSummaryOut,
    RecordIn,
    RecordOut,
)

logger = logging.getLogger(__name__)

# ─── API instance ────────────────────────────────────────────────────────────

api = NinjaAPI(
    version="1.0.0",
    title="Health Analytic Service",
    auth=ApiKeyAuth(),
    throttle=[AuthRateThrottle("100/min")],
)


@api.exception_handler(IntegrityError)
def integrity_error_handler(request: HttpRequest, exc: IntegrityError) -> HttpResponse:
    """Return 409 Conflict when a unique constraint is violated."""
    logger.warning("IntegrityError on %s %s: %s", request.method, request.path, exc)
    return api.create_response(
        request,
        {"detail": "A record with this identifier already exists."},
        status=409,
    )


# ─── Defaults ────────────────────────────────────────────────────────────────

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100

# ─── Patient CRUD ────────────────────────────────────────────────────────────

patient_router = Router(tags=["patients"])


@patient_router.post("/", response={201: PatientOut})
def create_patient(request: HttpRequest, payload: PatientIn) -> Tuple[int, Any]:
    """Create a new patient."""
    patient = Patient.objects.create(**payload.dict())
    return 201, patient


@patient_router.get("/", response=PaginatedPatientResponse)
def list_patients(
    request: HttpRequest,
    offset: int = Query(0),  # type: ignore[type-arg]  # noqa: B008
    limit: int = Query(_DEFAULT_LIMIT),  # type: ignore[type-arg]  # noqa: B008
) -> PaginatedPatientResponse:
    """Return paginated patient summaries (no PII)."""
    limit = min(limit, _MAX_LIMIT)
    qs = Patient.objects.all()
    count = qs.count()
    page = qs[offset:offset + limit]
    results: List[PatientSummaryOut] = [
        PatientSummaryOut(
            id=p.pk,
            patient_id=p.patient_id,
            patient_name=p.patient_name,
        )
        for p in page
    ]
    return PaginatedPatientResponse(count=count, results=results)


@patient_router.get("/{patient_id}", response=PatientOut)
def get_patient(request: HttpRequest, patient_id: str) -> Patient:
    """Return a single patient by ``patient_id``."""
    return get_object_or_404(Patient, patient_id=patient_id)


@patient_router.put("/{patient_id}", response=PatientOut)
def update_patient(request: HttpRequest, patient_id: str, payload: PatientIn) -> Patient:
    """Update an existing patient."""
    patient = get_object_or_404(Patient, patient_id=patient_id)
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(patient, attr, value)
    patient.save()
    return patient


@patient_router.delete("/{patient_id}", response={204: None})
def delete_patient(request: HttpRequest, patient_id: str) -> Tuple[int, None]:
    """Delete a patient by ``patient_id``."""
    patient = get_object_or_404(Patient, patient_id=patient_id)
    patient.delete()
    return 204, None


api.add_router("/patients/", patient_router)

# ─── Record ingest ───────────────────────────────────────────────────────────

record_router = Router(tags=["records"])


@record_router.post("/", response={200: RecordOut, 201: RecordOut})
def ingest_record(request: HttpRequest, payload: RecordIn) -> Tuple[int, RecordOut]:
    """Upsert an ED visit record (idempotent on ``record_id``).

    * If a ``patient_id`` is present the corresponding :class:`Patient` is
      fetched-or-created and any patient-level fields in the payload are used
      to update the patient row.
    * Only non-``None`` payload fields overwrite existing record values so that
      partial re-sends never erase previously ingested data.
    * Returns **201** when a new record is created, **200** when an existing
      record is updated.
    """
    data = payload.dict()

    # ── Resolve / upsert patient ─────────────────────────────────────────
    patient = None
    patient_id = data.pop("patient_id", None)
    patient_name = data.pop("patient_name", None)
    date_of_birth = data.pop("date_of_birth", None)
    ssn_last4 = data.pop("ssn_last4", None)
    contact_phone = data.pop("contact_phone", None)

    if patient_id is not None:
        patient_defaults = {}
        if patient_name is not None:
            patient_defaults["patient_name"] = patient_name
        if date_of_birth is not None:
            patient_defaults["date_of_birth"] = date_of_birth
        if ssn_last4 is not None:
            patient_defaults["ssn_last4"] = ssn_last4
        if contact_phone is not None:
            patient_defaults["contact_phone"] = contact_phone

        patient, _created = Patient.objects.get_or_create(
            patient_id=patient_id,
            defaults=patient_defaults,
        )
        # If the patient already existed, merge in any new non-null fields.
        if not _created and patient_defaults:
            for attr, value in patient_defaults.items():
                setattr(patient, attr, value)
            patient.save()

    # ── Upsert record ────────────────────────────────────────────────────
    record_id = data.pop("record_id")

    # Build defaults dict with only non-None values
    defaults = {k: v for k, v in data.items() if v is not None}
    if patient is not None:
        defaults["patient"] = patient

    record, created = Record.objects.get_or_create(
        record_id=record_id,
        defaults=defaults,
    )

    if not created and defaults:
        for attr, value in defaults.items():
            setattr(record, attr, value)
        record.save()

    # ── Assign record to a visit ─────────────────────────────────────────
    assign_record_to_visit(record)

    # Build response
    response_data = RecordOut(
        id=record.id,
        record_id=record.record_id,
        patient_id=record.patient.patient_id if record.patient else None,
        facility=record.facility,
        timestamp=record.timestamp,
        event_type=record.event_type,
        acuity_level=record.acuity_level,
        chief_complaint=record.chief_complaint,
        disposition=record.disposition,
        diagnosis_codes=record.diagnosis_codes,
        created=created,
    )

    status = 201 if created else 200
    return status, response_data


api.add_router("/records/", record_router)

# ─── Analytics (separate app) ───────────────────────────────────────────────
# Imported last to avoid circular imports.
from analytics.api import router as analytics_router  # noqa: E402

api.add_router("/analytics/", analytics_router)
