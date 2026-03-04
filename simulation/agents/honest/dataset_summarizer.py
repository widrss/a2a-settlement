"""Honest agent that summarizes data from a public API endpoint."""

from __future__ import annotations

import json

import httpx

from simulation.agents import HonestAgent, SimulationResult, SimulationTask


class DatasetSummarizer(HonestAgent):
    """Fetches real data from a public API and produces a summary."""

    def __init__(self):
        super().__init__("DatasetSummarizer")

    def execute(self, task: SimulationTask) -> SimulationResult:
        uri = task.params.get("uri", "https://httpbin.org/json")

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(uri)
                resp.raise_for_status()
                raw = resp.content
                data = resp.json()
        except Exception as exc:
            return SimulationResult(
                content=json.dumps({"error": str(exc)}),
                provenance=None,
                is_fabricated=False,
            )

        if isinstance(data, list):
            summary = f"Dataset contains {len(data)} records."
        elif isinstance(data, dict):
            summary = f"Dataset contains {len(data)} top-level keys: {', '.join(list(data.keys())[:10])}"
        else:
            summary = f"Dataset value: {str(data)[:500]}"

        return SimulationResult(
            content=summary,
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
                "attestation_level": "self_declared",
            },
            is_fabricated=False,
        )
