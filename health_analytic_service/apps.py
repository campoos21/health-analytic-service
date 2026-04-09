"""Application configuration for the health_analytic_service package."""

from django.apps import AppConfig


class HealthAnalyticServiceConfig(AppConfig):
    """Django app config for core models (Patient, Record, ApiKey)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "health_analytic_service"
    verbose_name = "Health Analytic Service"
