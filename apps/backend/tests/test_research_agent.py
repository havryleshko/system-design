import pytest

from apps.backend.app.agent.system_design import nodes
from apps.backend.app.agent.system_design.state import State


def test_research_agent_merges_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_kb(state: State) -> dict[str, object]:
        return {
            "source": "knowledge_base",
            "status": "completed",
            "highlights": ["KB summary"],
            "citations": [{"source": "kb", "url": "https://kb.example", "title": "KB"}],
            "risks": ["Needs compliance sign-off"],
        }

    def fake_gh(state: State) -> dict[str, object]:
        return {
            "source": "github_api",
            "status": "completed",
            "highlights": ["Repo description"],
            "citations": [{"source": "github_repo", "url": "https://github.com/org/repo"}],
            "risks": [],
        }

    def fake_search(state: State) -> dict[str, object]:
        return {
            "source": "web_search",
            "status": "completed",
            "highlights": ["External article"],
            "citations": [{"source": "web_search", "url": "https://example.com"}],
            "risks": ["Market risk"],
        }

    monkeypatch.setattr(nodes, "knowledge_base_node", fake_kb)
    monkeypatch.setattr(nodes, "github_api_node", fake_gh)
    monkeypatch.setattr(nodes, "web_search_node", fake_search)

    state: State = {
        "goal": "Build AI infra",
        "metadata": {},
    }

    result = nodes.research_agent(state)
    research_state = result["research_state"]

    assert result["run_phase"] == "design"
    assert research_state["status"] == "completed"
    assert set(research_state["nodes"].keys()) == {"knowledge_base", "github_api", "web_search"}
    assert "KB summary" in research_state["highlights"]
    assert "External article" in research_state["highlights"]
    assert research_state["risks"]
    assert result["research_summary"].startswith("- KB summary")


def test_research_agent_handles_missing_inputs() -> None:
    state: State = {
        "goal": "",
        "metadata": {},
    }

    result = nodes.research_agent(state)
    research_state = result["research_state"]

    assert result["run_phase"] == "design"
    assert research_state["status"] == "skipped"
    assert all(node["status"] == "skipped" for node in research_state["nodes"].values())
    assert not result["research_summary"]







