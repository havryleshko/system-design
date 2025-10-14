"""Predefined evaluation scenarios for the system design agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, List


@dataclass(slots=True)
class Scenario:
    """Minimal bundle of inputs and expectations for a run."""

    name: str
    prompt: str
    success_criteria: str


@dataclass(slots=True)
class ScenarioResult:
    scenario: Scenario
    output: str
    score: float
    passed: bool
    feedback: str


def default_scenarios() -> List[Scenario]:
    """Return the built-in scenarios covering representative tasks."""

    return [
        Scenario(
            name="crud_saas",
            prompt=(
                "Design a multi-tenant SaaS platform for managing invoices. "
                "Include auth, billing, tenant isolation, and analytics requirements."
            ),
            success_criteria=(
                "Must outline auth, data isolation, billing pipeline, and analytics flows."
            ),
        ),
        Scenario(
            name="streaming_analytics",
            prompt=(
                "Design a real-time streaming analytics system for IoT sensors sending telemetry every second."
            ),
            success_criteria=(
                "Need ingestion, stream processing, storage tiers, dashboards, and fault tolerance."
            ),
        ),
        Scenario(
            name="marketplace",
            prompt=(
                "Design a two-sided marketplace for freelancers and clients with discovery, payments, and dispute resolution."
            ),
            success_criteria=(
                "Should cover matching, payments/escrow, reviews, messaging, and trust & safety."
            ),
        ),
    ]


def load_scenarios(extra_path: str | Path | None = None) -> Iterator[Scenario]:
    """Yield scenarios, optionally extending with a newline-separated file."""

    for scen in default_scenarios():
        yield scen

    if extra_path is None:
        return

    path = Path(extra_path)
    if not path.exists():
        return

    for block in path.read_text(encoding="utf-8").split("\n\n"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        name, prompt, criteria = lines[:3]
        yield Scenario(name=name, prompt=prompt, success_criteria=criteria)


def iter_scenarios(items: Iterable[Scenario]) -> Iterator[Scenario]:
    """Simple generator wrapper to allow chaining without materialising lists."""

    for item in items:
        yield item


