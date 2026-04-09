"""Application configuration for the analytics app."""

from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """Django app config for analytical endpoints."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "analytics"
    verbose_name = "Analytics"
