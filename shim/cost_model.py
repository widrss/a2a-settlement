"""Cost model abstraction for the Security Shim.

Determines how much each proxied request costs against the escrow.
Ships with a flat-fee default and a per-destination model; callers
can subclass ``CostModel`` for custom pricing logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .models import ProxyRequest


class CostModel(ABC):
    """Base class for shim cost models."""

    @abstractmethod
    def compute_cost(self, request: ProxyRequest, destination_url: str) -> float:
        """Return the cost in credits for this proxied request."""
        ...


class FlatFeeCostModel(CostModel):
    """Every proxied request costs the same flat fee."""

    def __init__(self, fee: float = 1.0):
        self._fee = fee

    def compute_cost(self, request: ProxyRequest, destination_url: str) -> float:
        return self._fee


class PerDestinationCostModel(CostModel):
    """Cost varies by destination domain, with a flat-fee fallback.

    Usage::

        model = PerDestinationCostModel(
            default_fee=1.0,
            overrides={
                "api.github.com": 2.0,
                "lambda.us-east-1.amazonaws.com": 5.0,
                "hooks.slack.com": 0.5,
            },
        )
    """

    def __init__(
        self,
        default_fee: float = 1.0,
        overrides: Optional[dict[str, float]] = None,
    ):
        self._default = default_fee
        self._overrides = overrides or {}

    def compute_cost(self, request: ProxyRequest, destination_url: str) -> float:
        from urllib.parse import urlparse

        host = urlparse(destination_url).hostname or ""

        # Exact match first, then suffix match
        if host in self._overrides:
            return self._overrides[host]
        for domain, cost in self._overrides.items():
            if host.endswith(f".{domain}"):
                return cost
        return self._default
