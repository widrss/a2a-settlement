"""Adversarial agent that cites non-existent API endpoints."""

from __future__ import annotations

import json
import random
import string

from simulation.agents import AdversarialAgent, SimulationResult, SimulationTask

FAKE_DOMAINS = [
    "api.nonexistent-service-{rand}.io",
    "data.fake-government-{rand}.gov",
    "api.imaginary-provider-{rand}.com",
]


class FakeEndpointCiter(AdversarialAgent):
    """Generates data claiming to come from endpoints that don't exist."""

    def __init__(self):
        super().__init__("FakeEndpointCiter")

    def execute(self, task: SimulationTask) -> SimulationResult:
        rand = "".join(random.choices(string.ascii_lowercase, k=6))
        domain = random.choice(FAKE_DOMAINS).format(rand=rand)
        fake_uri = f"https://{domain}/v1/data"

        content = json.dumps(
            {
                "records": [
                    {
                        "id": i,
                        "value": f"record_{i}",
                        "score": round(random.random(), 4),
                    }
                    for i in range(10)
                ],
                "total": 10,
                "source": fake_uri,
            },
            indent=2,
        )

        return SimulationResult(
            content=content,
            provenance={
                "source_type": "api",
                "source_refs": [
                    {
                        "uri": fake_uri,
                        "method": "GET",
                        "timestamp": self._now_iso(),
                    }
                ],
                "attestation_level": "self_declared",
            },
            is_fabricated=True,
        )
