"""Analytics models – Visit aggregation for ED event records."""

from __future__ import annotations

from datetime import datetime

from django.db import models


class Visit(models.Model):
    """An aggregated ED visit grouping multiple event records for one patient.

    A visit spans from REGISTRATION to DEPARTURE. When boundary events are
    missing, the visit is still created using time-proximity heuristics and
    the ``is_registration_missing`` / ``is_departure_missing`` flags are set.

    Each event-stage timestamp is stored directly on the visit so the full
    timeline is available without joining back to the records table.
    """

    class Status(models.TextChoices):
        """Visit lifecycle status."""

        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        INCOMPLETE = "INCOMPLETE", "Incomplete"

    patient = models.ForeignKey(
        "health_analytic_service.Patient",
        on_delete=models.CASCADE,
        related_name="visits",
    )

    # ── Per-stage timestamps ─────────────────────────────────────────────
    registration_at = models.DateTimeField(null=True, blank=True)
    triage_at = models.DateTimeField(null=True, blank=True)
    bed_assignment_at = models.DateTimeField(null=True, blank=True)
    treatment_at = models.DateTimeField(null=True, blank=True)
    disposition_at = models.DateTimeField(null=True, blank=True)
    departure_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
    )
    is_registration_missing = models.BooleanField(
        default=False,
        help_text="True when no REGISTRATION event was found for this visit.",
    )
    is_departure_missing = models.BooleanField(
        default=False,
        help_text="True when no DEPARTURE event was found for this visit.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Visit."""

        ordering = ["-registration_at"]
        indexes = [
            models.Index(
                fields=["status", "is_registration_missing", "is_departure_missing"],
                name="ix_visit_status_flags",
            ),
        ]

    def __str__(self) -> str:
        """Return a readable representation of the visit."""
        return f"Visit {self.pk} – {self.patient} ({self.status})"

    @property
    def started_at(self) -> "datetime | None":
        """Earliest known event timestamp for this visit."""
        timestamps = [
            self.registration_at,
            self.triage_at,
            self.bed_assignment_at,
            self.treatment_at,
            self.disposition_at,
            self.departure_at,
        ]
        valid = [t for t in timestamps if t is not None]
        return min(valid) if valid else None

    @property
    def ended_at(self) -> "datetime | None":
        """Latest known event timestamp for this visit."""
        timestamps = [
            self.registration_at,
            self.triage_at,
            self.bed_assignment_at,
            self.treatment_at,
            self.disposition_at,
            self.departure_at,
        ]
        valid = [t for t in timestamps if t is not None]
        return max(valid) if valid else None
