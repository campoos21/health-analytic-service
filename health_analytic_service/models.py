"""Core domain models for the health analytic service."""

import secrets

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def generate_api_key() -> str:
    """Return a random 40-character hex string for use as an API key."""
    return secrets.token_hex(20)


class ApiKey(models.Model):
    """API key used for authenticating external clients."""

    key = models.CharField(
        max_length=100,
        unique=True,
        default=generate_api_key,
        db_index=True,
    )
    name = models.CharField(max_length=255, help_text="Human-readable label for this key.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options for ApiKey."""

        verbose_name = "API Key"
        verbose_name_plural = "API Keys"

    def __str__(self) -> str:
        """Return the key name and a masked preview."""
        return f"{self.name} ({self.key[:8]}…)"


class Patient(models.Model):
    """A patient that may appear across multiple ED visit records."""

    patient_id = models.CharField(max_length=255, unique=True)
    patient_name = models.CharField(max_length=255, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    ssn_last4 = models.CharField(max_length=4, null=True, blank=True)
    contact_phone = models.CharField(max_length=50, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Patient."""

        ordering = ["patient_id"]

    def __str__(self) -> str:
        """Return a readable representation of the patient."""
        return f"Patient {self.patient_id}"


class Record(models.Model):
    """A single ED visit event record (idempotent upsert on record_id)."""

    class EventType(models.TextChoices):
        """Allowed event types for ED visit records."""

        REGISTRATION = "REGISTRATION", "Registration"
        TRIAGE = "TRIAGE", "Triage"
        BED_ASSIGNMENT = "BED_ASSIGNMENT", "Bed Assignment"
        TREATMENT = "TREATMENT", "Treatment"
        DISPOSITION = "DISPOSITION", "Disposition"
        DEPARTURE = "DEPARTURE", "Departure"

    class DispositionChoice(models.TextChoices):
        """Allowed disposition outcomes."""

        DISCHARGED = "DISCHARGED", "Discharged"
        ADMITTED = "ADMITTED", "Admitted"
        TRANSFERRED = "TRANSFERRED", "Transferred"
        LEFT_WITHOUT_TREATMENT = "LEFT_WITHOUT_TREATMENT", "Left Without Treatment"

    record_id = models.CharField(max_length=255, unique=True)
    patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records",
    )
    visit = models.ForeignKey(
        "analytics.Visit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records",
    )
    facility = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
        null=True,
        blank=True,
    )
    acuity_level = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    chief_complaint = models.CharField(max_length=500, null=True, blank=True)
    disposition = models.CharField(
        max_length=30,
        choices=DispositionChoice.choices,
        null=True,
        blank=True,
    )
    diagnosis_codes = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for Record."""

        ordering = ["-timestamp", "record_id"]
        indexes = [
            models.Index(
                fields=["timestamp", "facility"],
                name="ix_record_ts_facility",
            ),
        ]

    def __str__(self) -> str:
        """Return a readable representation of the record."""
        return f"Record {self.record_id}"
