"""Django admin configuration for core models."""

from django.contrib import admin

from health_analytic_service.models import ApiKey, Patient, Record


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for API keys."""

    list_display = ("name", "key", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "key")
    readonly_fields = ("created_at",)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for patients."""

    list_display = ("patient_id", "patient_name", "date_of_birth", "contact_phone", "updated_at")
    search_fields = ("patient_id", "patient_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for ED visit records."""

    list_display = ("record_id", "patient", "event_type", "facility", "timestamp", "updated_at")
    list_filter = ("event_type", "disposition", "facility")
    search_fields = ("record_id", "patient__patient_id")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("patient",)
