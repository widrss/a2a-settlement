"""Escrow Gate -- checks and deducts escrow balance before proxying.

The gate talks to the exchange API to verify that the agent has an
active, funded escrow for the task. After a successful proxy, it
records the cost deduction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .cost_model import CostModel, FlatFeeCostModel
from .models import ProxyRequest

logger = logging.getLogger("shim.escrow_gate")


class InsufficientEscrowError(Exception):
    """Escrow balance is too low to cover the request cost."""

    def __init__(self, escrow_id: str, required: float, available: float):
        self.escrow_id = escrow_id
        self.required = required
        self.available = available
        super().__init__(
            f"Escrow {escrow_id}: need {required} credits but only {available} available"
        )


class EscrowNotFoundError(Exception):
    """The escrow does not exist or is not in 'held' status."""

    pass


@dataclass
class EscrowStatus:
    escrow_id: str
    status: str
    amount: int
    remaining: float


class EscrowGate:
    """Validates escrow funding and computes cost for each proxied request.

    In this reference implementation, the gate maintains a local ledger
    of deductions against each escrow for fast, synchronous checks.
    A production deployment would query the exchange API.
    """

    def __init__(self, cost_model: Optional[CostModel] = None, default_fee: float = 1.0):
        self._cost_model = cost_model or FlatFeeCostModel(default_fee)
        self._escrows: dict[str, EscrowStatus] = {}

    def register_escrow(self, escrow_id: str, amount: int, status: str = "held") -> None:
        """Register an escrow for tracking (called during setup or from exchange webhook)."""
        self._escrows[escrow_id] = EscrowStatus(
            escrow_id=escrow_id,
            status=status,
            amount=amount,
            remaining=float(amount),
        )

    def get_status(self, escrow_id: str) -> Optional[EscrowStatus]:
        return self._escrows.get(escrow_id)

    def check_and_deduct(
        self,
        request: ProxyRequest,
        destination_url: str,
        cost_override: Optional[float] = None,
    ) -> float:
        """Verify the escrow can cover the cost and deduct it.

        Returns the cost charged.

        Raises:
            EscrowNotFoundError: Escrow not found or not held.
            InsufficientEscrowError: Balance too low.
        """
        escrow = self._escrows.get(request.escrow_id)
        if escrow is None:
            raise EscrowNotFoundError(
                f"Escrow {request.escrow_id} not found in gate"
            )
        if escrow.status != "held":
            raise EscrowNotFoundError(
                f"Escrow {request.escrow_id} is '{escrow.status}', not 'held'"
            )

        cost = cost_override if cost_override is not None else self._cost_model.compute_cost(request, destination_url)

        if escrow.remaining < cost:
            raise InsufficientEscrowError(
                escrow_id=request.escrow_id,
                required=cost,
                available=escrow.remaining,
            )

        escrow.remaining -= cost
        logger.info(
            "Escrow %s: deducted %.2f, remaining %.2f",
            request.escrow_id, cost, escrow.remaining,
        )
        return cost
