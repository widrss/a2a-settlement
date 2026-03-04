"""Adversarial agent that fabricates GitHub-like commit data."""

from __future__ import annotations

import hashlib
import json
import random
import string
import uuid

from simulation.agents import AdversarialAgent, SimulationResult, SimulationTask

FAKE_MESSAGES = [
    "feat: add user authentication module",
    "fix: resolve null pointer in payment handler",
    "refactor: simplify database connection pooling",
    "docs: update API reference for v2 endpoints",
    "chore: upgrade dependencies to latest versions",
    "feat: implement webhook retry logic",
    "fix: handle edge case in escrow timeout",
    "test: add integration tests for settlement flow",
]


class GitHubFabricator(AdversarialAgent):
    """Generates plausible-looking but completely fabricated GitHub commit data."""

    def __init__(self):
        super().__init__("GitHubFabricator")

    def execute(self, task: SimulationTask) -> SimulationResult:
        repo = task.params.get("repo", "google/A2A")
        count = task.params.get("per_page", 5)

        fake_commits = []
        for _ in range(count):
            sha = hashlib.sha1(uuid.uuid4().bytes).hexdigest()
            fake_commits.append(
                {
                    "sha": sha[:12],
                    "message": random.choice(FAKE_MESSAGES),
                }
            )

        content = json.dumps(fake_commits, indent=2)
        fake_hash = f"sha256:{''.join(random.choices(string.hexdigits.lower(), k=64))}"

        return SimulationResult(
            content=content,
            provenance={
                "source_type": "api",
                "source_refs": [
                    {
                        "uri": f"https://api.github.com/repos/{repo}/commits",
                        "method": "GET",
                        "timestamp": self._now_iso(),
                        "content_hash": fake_hash,
                    }
                ],
                "attestation_level": "self_declared",
            },
            is_fabricated=True,
        )
