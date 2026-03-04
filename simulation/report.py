"""Report generator — produces publishable results from simulation runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from simulation.runner import SimulationRun
from simulation.scorer import ScoreCard, score_runs


def generate_report(
    runs: list[SimulationRun],
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive report from simulation runs.

    Returns the report dict and optionally writes to files.
    """
    card = score_runs(runs)
    total_scenarios = len(runs)
    total_time = sum(r.finished_at - r.started_at for r in runs)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "scenarios_run": total_scenarios,
            "total_transactions": card.total_transactions,
            "total_honest_agents": card.total_honest,
            "total_adversarial_agents": card.total_adversarial,
            "total_time_seconds": round(total_time, 2),
        },
        "detection": {
            "detection_rate": card.detection_rate,
            "false_positive_rate": card.false_positive_rate,
            "precision": card.precision,
            "true_positives": card.true_positives,
            "false_negatives": card.false_negatives,
            "true_negatives": card.true_negatives,
            "false_positives": card.false_positives,
        },
        "economics": {
            "escrow_protected": card.escrow_protected,
        },
        "performance": {
            "avg_verification_latency_ms": card.avg_latency_ms,
        },
        "scorecard": card.as_dict(),
    }

    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_json(report, output_dir / "report.json")
        _write_markdown(report, card, output_dir / "report.md")

    return report


def _write_json(report: dict[str, Any], path: Path) -> None:
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)


def _write_markdown(report: dict[str, Any], card: ScoreCard, path: Path) -> None:
    summary = report["summary"]
    detection = report["detection"]
    econ = report["economics"]
    perf = report["performance"]

    lines = [
        "# A2A-SE Provenance Attestation — Simulation Report",
        "",
        f"**Generated:** {report['generated_at']}",
        "",
        "## Summary",
        "",
        f"- **Scenarios run:** {summary['scenarios_run']}",
        f"- **Total transactions:** {summary['total_transactions']}",
        f"- **Honest agents:** {summary['total_honest_agents']}",
        f"- **Adversarial agents:** {summary['total_adversarial_agents']}",
        f"- **Total time:** {summary['total_time_seconds']:.2f}s",
        "",
        "## Detection Results",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Detection rate | {detection['detection_rate']:.1%} |",
        f"| False positive rate | {detection['false_positive_rate']:.1%} |",
        f"| Precision | {detection['precision']:.1%} |",
        f"| True positives | {detection['true_positives']} |",
        f"| False negatives | {detection['false_negatives']} |",
        f"| True negatives | {detection['true_negatives']} |",
        f"| False positives | {detection['false_positives']} |",
        "",
        "## Economic Impact",
        "",
        f"- **Escrow value protected:** {econ['escrow_protected']} ATE",
        "",
        "## Performance",
        "",
        f"- **Avg verification latency:** {perf['avg_verification_latency_ms']:.1f}ms",
        "",
        "---",
        "",
        (
            f"Across {summary['total_transactions']} simulated agent-to-agent transactions, "
            f"A2A-SE provenance verification detected **{detection['detection_rate']:.0%}** of fabricated "
            f"deliverables. False positive rate: **{detection['false_positive_rate']:.0%}**. "
            f"Average verification overhead: **{perf['avg_verification_latency_ms']:.0f}ms**."
        ),
    ]

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
