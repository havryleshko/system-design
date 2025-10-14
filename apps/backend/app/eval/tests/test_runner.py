from unittest.mock import Mock

from app.eval.judge import LLMJudge, Judgement
from app.eval.runner import run_scenario
from app.eval.scenarios import Scenario


class DummyJudge(LLMJudge):
    def __init__(self):
        super().__init__(model="dummy")

    def judge(self, prompt: str, output: str, criteria: str) -> Judgement:  # type: ignore[override]
        return Judgement(score=0.5, passed=True, feedback="ok")


def test_run_scenario_invokes_graph(monkeypatch):
    scenario = Scenario(name="test", prompt="Design X", success_criteria="covers X")

    mock_state = {"output": "Result markdown"}
    fake_invoke = Mock(return_value=mock_state)

    class DummyModule:
        class Graph:
            @staticmethod
            def invoke(state):
                return fake_invoke(state)

        graph = Graph()

    def fake_import(name: str):
        assert name == "app.agent.system_design.graph"
        return DummyModule()

    monkeypatch.setattr("app.eval.runner.importlib.import_module", fake_import)

    judge = DummyJudge()
    result = run_scenario(scenario, judge)

    fake_invoke.assert_called_once()
    assert result.score == 0.5
    assert result.output == "Result markdown"

