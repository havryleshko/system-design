from app.eval.scenarios import default_scenarios


def test_default_scenarios_non_empty():
    scenarios = default_scenarios()
    assert len(scenarios) >= 3
    names = {s.name for s in scenarios}
    assert {"crud_saas", "streaming_analytics", "marketplace"}.issubset(names)

