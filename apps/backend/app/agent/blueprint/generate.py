from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage
from app.agent.llm import call_llm_structured
from .schema import Blueprint

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_blueprint(*, goal: str, clarifier_summary: Optional[str] = None) -> Blueprint:
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal is required")

    clar = (clarifier_summary or "").strip()
    context = f"\n\nClarifier summary:\n{clar}\n" if clar else ""

    sys = SystemMessage(
        content=(
            "You generate a deployable multi-agent architecture blueprint.\n"
            "Output MUST conform to the provided schema.\n"
            "Rules:\n"
            "- Keep it simple. No jargon.\n"
            "- Use the amount of agents needed to achieve the goal. Give each a concrete, goal-specific name.\n"
            "- Each agent must have: id, name, role.\n"
            "- Build a graph with nodes/edges that makes the control flow legible.\n"
            "- Graph nodes of type 'agent' MUST reference an existing agent_id.\n"
            "- Include 'start' and 'end' nodes.\n"
            "- Prefer control edges for sequencing; use data edges only when helpful.\n"
            "- Use stable snake_case ids.\n"
        )
    )

    user = HumanMessage(
        content=(
            f"Goal:\n{goal}\n"
            f"{context}\n"
            "Generate the blueprint now."
        )
    )

    bp = call_llm_structured([sys, user], Blueprint, retries=2)
    if not (bp.generated_at or "").strip():
        bp.generated_at = _now_iso()
    if bp.goal.strip() != goal:
        bp.goal = goal

    return bp

