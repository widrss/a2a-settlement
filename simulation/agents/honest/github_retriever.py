"""Honest agent that retrieves real data from the GitHub API."""

from __future__ import annotations

import json

import httpx

from simulation.agents import HonestAgent, SimulationResult, SimulationTask


class GitHubRetriever(HonestAgent):
    """Fetches real commit history from a public GitHub repository."""

    def __init__(self):
        super().__init__("GitHubRetriever")

    def execute(self, task: SimulationTask) -> SimulationResult:
        repo = task.params.get("repo", "google/A2A")
        uri = f"https://api.github.com/repos/{repo}/commits"
        params = {"per_page": task.params.get("per_page", 5)}

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(uri, params=params)
                resp.raise_for_status()
                raw = resp.content
                data = resp.json()
        except Exception as exc:
            return SimulationResult(
                content=json.dumps({"error": str(exc)}),
                provenance=None,
                is_fabricated=False,
            )

        content = json.dumps(
            [
                {"sha": c["sha"][:12], "message": c["commit"]["message"][:100]}
                for c in data
            ],
            indent=2,
        )

        return SimulationResult(
            content=content,
            provenance={
                "source_type": "api",
                "source_refs": [
                    {
                        "uri": uri,
                        "method": "GET",
                        "timestamp": self._now_iso(),
                        "content_hash": self._hash_content(raw),
                    }
                ],
                "attestation_level": "signed",
                "signature": resp.headers.get("x-request-id", ""),
            },
            is_fabricated=False,
        )
