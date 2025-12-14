import json
import pytest

from apps.backend.app.agent.system_design import nodes
from apps.backend.app.agent.system_design.state import State


def test_planner_scope_marks_clarifier_when_goal_missing() -> None:
    state: State = {
        "goal": "",
        "messages": [],
    }

    result = nodes.planner_scope(state)
    scope = result["plan_scope"]

    assert scope["needs_clarifier"] is True
    assert scope["blocking_issues"]
    assert scope["status"] == "completed"


def test_planner_steps_merges_risks_and_triggers_quality_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call_brain(messages, **kwargs) -> str:  # type: ignore[no-untyped-def]
        return json.dumps(
            {
                "steps": [
                    {"id": "plan-1", "title": "Outline MVP", "detail": "Build core service"},
                    {"id": "plan-2", "title": "Ship Beta", "detail": "Launch to pilot users"},
                ],
                "risks": ["LLM risk"],
            }
        )

    monkeypatch.setattr(nodes, "call_brain", fake_call_brain)

    scope = {
        "goal": "Create a resilient API gateway",
        "latest_input": "Must support 1M users",
        "memory_highlights": [],
        "issues": ["Need compliance review"],
        "blocking_issues": ["Missing SLA", "Unclear budget"],
        "info_issues": ["Need regulatory constraints"],
        "risks": ["Existing risk"],
        "needs_clarifier": False,
        "status": "completed",
    }
    state: State = {
        "goal": scope["goal"],
        "plan_scope": scope,
    }

    step_updates = nodes.planner_steps(state)
    plan_state = step_updates["plan_state"]

    assert set(plan_state["risks"]) == {"Existing risk", "LLM risk"}

    retry_result = nodes.planner_agent(
        {
            "plan_scope": scope,
            "plan_state": plan_state,
            "metadata": {},
        }
    )

    assert retry_result["plan_state"] == {}
    assert retry_result["metadata"]["planner_quality_retry"] is True
    assert retry_result["run_phase"] == "planner"


def test_planner_agent_emits_summary_and_records_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_record(state: State, summary: str) -> None:
        captured["state"] = state
        captured["summary"] = summary

    monkeypatch.setattr(nodes, "_record_final_plan_memory", fake_record)

    plan_state = {
        "status": "completed",
        "summary": "Clear, user-facing rollout plan.",
        "quality": 0.82,
        "steps": [{"id": "plan-1", "title": "Draft plan", "detail": "Write summary"}],
    }
    state: State = {
        "plan_scope": {
            "status": "completed",
            "needs_clarifier": False,
        },
        "plan_state": plan_state,
        "metadata": {"user_id": "user-1", "thread_id": "thread-1"},
        "messages": [],
    }

    result = nodes.planner_agent(state)

    assert result["plan"] == "Clear, user-facing rollout plan."
    assert result["plan_quality"] == pytest.approx(0.82)
    assert result["run_phase"] == "research"
    assert captured["summary"] == "Clear, user-facing rollout plan."
    assert captured["state"] is state

