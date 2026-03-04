"""Simulation agent base classes and registry."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class SimulationTask:
    """A task to be executed by a simulation agent."""

    task_id: str
    task_type: str
    description: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationResult:
    """Result of a simulation agent's execution."""

    content: str
    provenance: dict[str, Any] | None = None
    is_fabricated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class SimulationAgent(ABC):
    """Base class for all simulation agents."""

    def __init__(self, name: str, agent_type: str):
        self.name = name
        self.agent_type = agent_type

    @abstractmethod
    def execute(self, task: SimulationTask) -> SimulationResult:
        """Execute a task and return content with optional provenance."""
        ...

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _hash_content(content: str | bytes) -> str:
        if isinstance(content, str):
            content = content.encode("utf-8")
        return f"sha256:{hashlib.sha256(content).hexdigest()}"


class HonestAgent(SimulationAgent):
    """Base for agents that use real data sources."""

    def __init__(self, name: str):
        super().__init__(name, "honest")


class AdversarialAgent(SimulationAgent):
    """Base for agents that fabricate data."""

    def __init__(self, name: str):
        super().__init__(name, "adversarial")
