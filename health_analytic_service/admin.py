"""Django admin configuration for core models."""

from typing import Any, Optional

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

from health_analytic_service.models import ApiKey, Patient, Record


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Admin view for API keys.

    The full key is shown only once, immediately after creation.  In the
    list view and on subsequent edits only a masked prefix is displayed.
    """

    list_display = ("name", "masked_key", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("created_at",)

    # Track the pk of a just-created key so we can show it once.
    _just_created_pk: Optional[int] = None

    @admin.display(description="API Key")
    def masked_key(self, obj: ApiKey) -> str:
        """Show only the first 8 chars followed by ``***``."""
        return f"{obj.key[:8]}***"

    def get_readonly_fields(
        self, request: HttpRequest, obj: Optional[ApiKey] = None,
    ) -> tuple[str, ...]:
        """Make ``key`` read-only after creation (cannot be changed)."""
        if obj is not None:
            return ("key", "created_at")
        return ("created_at",)

    def save_model(
        self, request: HttpRequest, obj: ApiKey, form: Any, change: bool,
    ) -> None:
        """Persist the key and remember its pk if newly created."""
        super().save_model(request, obj, form, change)
        if not change:
            self._just_created_pk = obj.pk

    def response_add(
        self, request: HttpRequest, obj: ApiKey, post_url_continue: Optional[str] = None,
    ) -> Any:
        """After adding, flash the full key to the user exactly once."""
        from django.contrib import messages

        messages.success(
            request,
            format_html(
                "API key created \u2014 copy it now, it will not be shown again: "
                "<code style='user-select:all'>{}</code>",
                obj.key,
            ),
        )
        self._just_created_pk = None
        return super().response_add(request, obj, post_url_continue)


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
