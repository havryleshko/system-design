from unittest.mock import Mock

from app.eval.judge import LLMJudge, Judgement
from app.eval.runner import run_scenario
from app.eval.scenarios import Scenario


class DummyJudge(LLMJudge):
    def __init__(self):
        super().__init__(model="dummy")

    def judge(self, prompt: str, output: str, criteria: str) -> Judgement: 
        return Judgement(score=0.5, passed=True, feedback="ok")


def test_run_scenario_invokes_graph(monkeypatch):
    scenario = Scenario(name="test", prompt="Design X", success_criteria="covers X")

    fake_generate = Mock(return_value=Mock(model_dump=lambda: {"version": "v1"}))
    monkeypatch.setattr("app.eval.runner.generate_blueprint", fake_generate)

    judge = DummyJudge()
    result = run_scenario(scenario, judge)

    fake_generate.assert_called_once()
    assert result.score == 0.5
    assert '"version": "v1"' in result.output

