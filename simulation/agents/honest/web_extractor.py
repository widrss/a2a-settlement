"""Honest agent that extracts content from a real web URL."""

from __future__ import annotations

import httpx

from simulation.agents import HonestAgent, SimulationResult, SimulationTask


class WebExtractor(HonestAgent):
    """Fetches and summarizes content from a target URL."""

    def __init__(self):
        super().__init__("WebExtractor")

    def execute(self, task: SimulationTask) -> SimulationResult:
        url = task.params.get("url", "https://httpbin.org/json")

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                raw = resp.content
                text = resp.text[:2000]
        except Exception as exc:
            return SimulationResult(
                content=f"Error fetching {url}: {exc}",
                provenance=None,
                is_fabricated=False,
            )

        return SimulationResult(
            content=f"Content from {url} ({len(raw)} bytes):\n{text}",
            provenance={
                "source_type": "web",
                "source_refs": [
                    {
                        "uri": url,
                        "method": "GET",
                        "timestamp": self._now_iso(),
                        "content_hash": self._hash_content(raw),
                    }
                ],
                "attestation_level": "self_declared",
            },
            is_fabricated=False,
        )
