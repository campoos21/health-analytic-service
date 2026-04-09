"""Analytical stub endpoints.

These will be fleshed out later. For now they return ``200 {}``.
"""

from django.http import HttpRequest
from ninja import Router

router = Router(tags=["analytics"])


@router.get("/analytical_endpoint_1")
def analytical_endpoint_1(request: HttpRequest) -> dict[str, str]:
    """Stub – analytical endpoint 1."""
    return {}


@router.get("/analytical_endpoint_2")
def analytical_endpoint_2(request: HttpRequest) -> dict[str, str]:
    """Stub – analytical endpoint 2."""
    return {}
