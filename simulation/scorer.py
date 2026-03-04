"""Scoring module — calculates detection rates, false positives, and latency metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from simulation.runner import SimulationRun


@dataclass
class ScoreCard:
    """Aggregate metrics across simulation runs."""

    total_transactions: int = 0
    total_honest: int = 0
    total_adversarial: int = 0

    # Detection
    true_positives: int = 0  # Fabricated AND flagged/rejected
    false_negatives: int = 0  # Fabricated AND approved
    true_negatives: int = 0  # Honest AND approved
    false_positives: int = 0  # Honest AND flagged/rejected

    # Economic
    escrow_protected: int = 0  # Sum of escrows where fabrication was caught

    # Latency
    latencies_ms: list[int] = field(default_factory=list)

    @property
    def detection_rate(self) -> float:
        total = self.true_positives + self.false_negatives
        return self.true_positives / total if total > 0 else 0.0

    @property
    def false_positive_rate(self) -> float:
        total = self.true_negatives + self.false_positives
        return self.false_positives / total if total > 0 else 0.0

    @property
    def precision(self) -> float:
        total = self.true_positives + self.false_positives
        return self.true_positives / total if total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return (
            sum(self.latencies_ms) / len(self.latencies_ms)
            if self.latencies_ms
            else 0.0
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_transactions": self.total_transactions,
            "total_honest": self.total_honest,
            "total_adversarial": self.total_adversarial,
            "true_positives": self.true_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "detection_rate": round(self.detection_rate, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "precision": round(self.precision, 4),
            "escrow_protected": self.escrow_protected,
            "avg_latency_ms": round(self.avg_latency_ms, 1),
        }


def _is_flagged(verification_result: dict[str, Any] | None) -> bool:
    """Determine if a verification result represents a flag/rejection."""
    if not verification_result:
        return False
    recommendation = verification_result.get("recommendation", "approve")
    return recommendation in ("flag", "reject")


def score_run(run: SimulationRun) -> ScoreCard:
    """Score a single simulation run."""
    card = ScoreCard()

    for tx in run.transactions:
        card.total_transactions += 1

        if tx.agent_type == "honest":
            card.total_honest += 1
        else:
            card.total_adversarial += 1

        flagged = _is_flagged(tx.verification_result)

        if tx.is_fabricated and flagged:
            card.true_positives += 1
            card.escrow_protected += tx.escrow_amount
        elif tx.is_fabricated and not flagged:
            card.false_negatives += 1
        elif not tx.is_fabricated and not flagged:
            card.true_negatives += 1
        elif not tx.is_fabricated and flagged:
            card.false_positives += 1

        if tx.verification_latency_ms > 0:
            card.latencies_ms.append(tx.verification_latency_ms)

    return card


def score_runs(runs: list[SimulationRun]) -> ScoreCard:
    """Aggregate scores across multiple simulation runs."""
    combined = ScoreCard()

    for run in runs:
        card = score_run(run)
        combined.total_transactions += card.total_transactions
        combined.total_honest += card.total_honest
        combined.total_adversarial += card.total_adversarial
        combined.true_positives += card.true_positives
        combined.false_negatives += card.false_negatives
        combined.true_negatives += card.true_negatives
        combined.false_positives += card.false_positives
        combined.escrow_protected += card.escrow_protected
        combined.latencies_ms.extend(card.latencies_ms)

    return combined
