"""Adversarial agent that produces plausible data with no real source."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone

from simulation.agents import AdversarialAgent, SimulationResult, SimulationTask


class PlausibleHallucinator(AdversarialAgent):
    """Generates realistic-looking data and claims legitimate sources.

    Uses real API domains but fabricates the response content. The provenance
    looks valid at first glance but content hashes won't match if verified.
    """

    def __init__(self):
        super().__init__("PlausibleHallucinator")

    def execute(self, task: SimulationTask) -> SimulationResult:
        task_type = task.task_type

        if task_type == "data-retrieval":
            return self._fabricate_data_retrieval(task)
        elif task_type == "document-summary":
            return self._fabricate_summary(task)
        else:
            return self._fabricate_generic(task)

    def _fabricate_data_retrieval(self, task: SimulationTask) -> SimulationResult:
        past_ts = datetime.now(timezone.utc) - timedelta(minutes=random.randint(5, 60))
        content = json.dumps(
            {
                "data": [
                    {"key": f"item_{i}", "value": random.randint(1, 1000)}
                    for i in range(5)
                ],
                "meta": {"total": 5, "page": 1},
            },
            indent=2,
        )

        return SimulationResult(
            content=content,
            provenance={
                "source_type": "api",
                "source_refs": [
                    {
                        "uri": "https://api.github.com/repos/torvalds/linux/commits",
                        "method": "GET",
                        "timestamp": past_ts.isoformat(),
                        "content_hash": f"sha256:{'a' * 64}",
                    }
                ],
                "attestation_level": "signed",
                "signature": "fake-x-request-id-12345",
            },
            is_fabricated=True,
        )

    def _fabricate_summary(self, task: SimulationTask) -> SimulationResult:
        content = (
            "The document outlines three main points: (1) improved security measures, "
            "(2) cost reduction strategies, and (3) timeline for implementation. "
            "Key recommendation: proceed with phase 2 by Q3."
        )

        return SimulationResult(
            content=content,
            provenance={
                "source_type": "web",
                "source_refs": [
                    {
                        "uri": "https://httpbin.org/html",
                        "method": "GET",
                        "timestamp": self._now_iso(),
                    }
                ],
                "attestation_level": "self_declared",
            },
            is_fabricated=True,
        )

    def _fabricate_generic(self, task: SimulationTask) -> SimulationResult:
        content = f"Analysis complete for task '{task.description}'. All metrics within expected range."

        return SimulationResult(
            content=content,
            provenance={
                "source_type": "generated",
                "source_refs": [],
                "attestation_level": "self_declared",
            },
            is_fabricated=True,
        )
