"""Simulation runner — orchestrates transactions through the exchange.

Assigns honest and adversarial agents to tasks from scenario YAML files,
runs them through the provenance verification pipeline, and captures
results for scoring.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from simulation.agents import (
    AdversarialAgent,
    HonestAgent,
    SimulationAgent,
    SimulationTask,
)
from simulation.agents.adversarial.fake_endpoint_citer import FakeEndpointCiter
from simulation.agents.adversarial.github_fabricator import GitHubFabricator
from simulation.agents.adversarial.plausible_hallucinator import PlausibleHallucinator
from simulation.agents.honest.dataset_summarizer import DatasetSummarizer
from simulation.agents.honest.github_retriever import GitHubRetriever
from simulation.agents.honest.web_extractor import WebExtractor

logger = logging.getLogger(__name__)

HONEST_AGENTS: list[type[HonestAgent]] = [
    GitHubRetriever,
    WebExtractor,
    DatasetSummarizer,
]

ADVERSARIAL_AGENTS: list[type[AdversarialAgent]] = [
    GitHubFabricator,
    FakeEndpointCiter,
    PlausibleHallucinator,
]


@dataclass
class TransactionRecord:
    """Record of a single simulated transaction."""

    task_id: str
    task_type: str
    agent_name: str
    agent_type: str  # "honest" or "adversarial"
    is_fabricated: bool
    provenance: dict[str, Any] | None
    verification_result: dict[str, Any] | None = None
    verification_latency_ms: int = 0
    escrow_amount: int = 0


@dataclass
class SimulationRun:
    """Complete simulation run with all transaction records."""

    scenario_name: str
    transactions: list[TransactionRecord] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0


def load_scenario(path: Path) -> dict[str, Any]:
    """Load a scenario YAML file."""
    with open(path) as f:
        return yaml.safe_load(f)


def run_scenario(
    scenario_path: Path,
    *,
    honest_ratio: float = 0.5,
    verify: bool = True,
) -> SimulationRun:
    """Run a single scenario with a mix of honest and adversarial agents.

    Args:
        scenario_path: Path to the scenario YAML file.
        honest_ratio: Fraction of tasks assigned to honest agents (0.0-1.0).
        verify: Whether to run provenance verification on results.

    Returns:
        SimulationRun with all transaction records.
    """
    import random

    from a2a_settlement_mediator.provenance import ProvenanceVerifier

    scenario = load_scenario(scenario_path)
    run = SimulationRun(
        scenario_name=scenario.get("name", scenario_path.stem),
        started_at=time.time(),
    )

    tasks = scenario.get("tasks", [])
    attestation_level = scenario.get("attestation_level", "self_declared")
    escrow_amount = scenario.get("escrow_amount", 50)

    honest_pool = [cls() for cls in HONEST_AGENTS]
    adversarial_pool = [cls() for cls in ADVERSARIAL_AGENTS]

    verifier = ProvenanceVerifier(spot_check_rate=0.0) if verify else None

    for task_def in tasks:
        sim_task = SimulationTask(
            task_id=task_def["id"],
            task_type=task_def.get("type", "data-retrieval"),
            description=task_def.get("description", ""),
            params=task_def.get("params", {}),
        )

        use_honest = random.random() < honest_ratio
        if use_honest:
            agent: SimulationAgent = random.choice(honest_pool)
        else:
            agent = random.choice(adversarial_pool)

        result = agent.execute(sim_task)

        verification_result = None
        verification_latency_ms = 0

        if verify and verifier and result.provenance:
            t0 = time.monotonic()
            loop = asyncio.new_event_loop()
            try:
                prov_result = loop.run_until_complete(
                    verifier.verify(
                        provenance=result.provenance,
                        deliverable_content=result.content,
                        tier=attestation_level,
                    )
                )
                verification_result = prov_result.model_dump()
            except Exception as exc:
                verification_result = {"error": str(exc)}
            finally:
                loop.close()
            verification_latency_ms = int((time.monotonic() - t0) * 1000)

        record = TransactionRecord(
            task_id=sim_task.task_id,
            task_type=sim_task.task_type,
            agent_name=agent.name,
            agent_type=agent.agent_type,
            is_fabricated=result.is_fabricated,
            provenance=result.provenance,
            verification_result=verification_result,
            verification_latency_ms=verification_latency_ms,
            escrow_amount=escrow_amount,
        )
        run.transactions.append(record)

        logger.info(
            "Task %s: agent=%s type=%s fabricated=%s verified=%s",
            sim_task.task_id,
            agent.name,
            agent.agent_type,
            result.is_fabricated,
            verification_result.get("verified") if verification_result else "N/A",
        )

    run.finished_at = time.time()
    return run


def run_all_scenarios(
    scenarios_dir: Path | None = None,
    *,
    honest_ratio: float = 0.5,
    repetitions: int = 1,
) -> list[SimulationRun]:
    """Run all scenario YAML files in the given directory."""
    if scenarios_dir is None:
        scenarios_dir = Path(__file__).parent / "scenarios"

    runs = []
    for scenario_file in sorted(scenarios_dir.glob("*.yaml")):
        for _ in range(repetitions):
            run = run_scenario(scenario_file, honest_ratio=honest_ratio)
            runs.append(run)
    return runs
