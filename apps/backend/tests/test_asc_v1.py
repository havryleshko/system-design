from apps.backend.app.agent.system_design import nodes
from apps.backend.app.agent.system_design.state import State


def test_evals_agent_emits_asc_v1_under_design_state() -> None:
    state: State = {
        "goal": "Build an agent system starter kit",
        "plan_state": {
            "status": "completed",
            "summary": "Build an MVP agent workflow and harden it for production.",
            "intermediate_milestones": ["MVP", "Beta", "Prod"],
            "steps": [
                {"id": "s1", "title": "Define scope", "detail": "Capture requirements and constraints."},
                {"id": "s2", "title": "Implement agents", "detail": "Wire tool calls and memory."},
            ],
        },
        "plan_scope": {
            "status": "completed",
            "blocking_issues": ["Missing SLA"],
            "info_issues": ["Unknown budget"],
            "risks": ["Tool API rate limits"],
        },
        "research_state": {
            "status": "completed",
            "highlights": ["Use retries and circuit breakers around tool calls."],
            "citations": [{"source": "web_search", "url": "https://example.com", "title": "Example"}],
            "risks": ["Hallucination risk"],
        },
        "critic_state": {
            "status": "completed",
            "notes": ["Add eval harness before shipping."],
            "review": {"status": "completed", "notes": ["Looks implementable."]},
        },
        "eval_state": {
            "telemetry": {
                "status": "completed",
                "telemetry": {"latency": {"p50_ms": 120, "p95_ms": 400}, "error_rate": 0.02},
                "notes": ["Rough estimate based on typical agent runs."],
            }
        },
        "design_state": {
            "status": "completed",
            "architecture": {
                "status": "completed",
                "architecture": {
                    "overview": "Two-agent system with tools and memory.",
                    "agents": [{"id": "a1", "name": "Coordinator", "responsibility": "Routes work", "tools": []}],
                    "tools": [{"id": "t1", "name": "Search", "type": "search"}],
                    "memory": {"short_term": {"purpose": "context", "implementation": "in-memory"}},
                    "control_loop": {"flow": "START -> a1 -> END"},
                    "bounded_autonomy": {"constraints": []},
                    "interactions": [{"source": "a1", "target": "t1", "kind": "tool_call"}],
                },
                "notes": [],
            },
            "output": {"status": "completed", "formatted_output": "# Output"},
            "notes": [],
        },
    }

    result = nodes.evals_agent(state)
    design_state = result.get("design_state") or {}
    assert isinstance(design_state, dict)

    asc = design_state.get("asc_v1")
    assert isinstance(asc, dict)
    assert asc.get("version") == "v1"
    assert asc.get("goal")


