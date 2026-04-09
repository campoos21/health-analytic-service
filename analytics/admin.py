"""Django admin for the analytics app."""

from django.contrib import admin

from analytics.models import Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for visits."""

    list_display = (
        "id",
        "patient",
        "status",
        "started_at",
        "ended_at",
        "is_registration_missing",
        "is_departure_missing",
        "created_at",
    )
    list_filter = ("status", "is_registration_missing", "is_departure_missing")
    search_fields = ("patient__patient_id",)
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("patient",)
