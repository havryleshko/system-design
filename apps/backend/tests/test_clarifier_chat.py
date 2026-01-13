from __future__ import annotations

import types

import app.agent.clarifier as clarifier


def test_clarifier_engine_questions(monkeypatch) -> None:
    def fake_call_llm_structured(messages, schema, **kwargs):
        return clarifier.ClarifierStructuredOutput(
            version="v1",
            type="question",
            assistant_message="What is your SLA?",
            question=clarifier.ClarifierQuestion(
                id="q1",
                text="What is your SLA?",
                priority="blocking",
                suggested_answers=["99.9%", "99.99%", "best effort"],
            ),
            missing_fields=["sla"],
            assumptions=[],
        )

    monkeypatch.setattr(clarifier, "call_llm_structured", fake_call_llm_structured)

    out = clarifier.run_clarifier(original_input="Build X", transcript=[], turn_count=0, force_stop=False)
    assert out.kind == "active"
    assert "SLA" in out.assistant_message
    assert out.questions and out.questions[0]["id"] == "q1"
    assert "99.9%" in out.questions[0]["suggested_answers"]


def test_clarifier_engine_stop(monkeypatch) -> None:
    def fake_call_llm_structured(messages, schema, **kwargs):
        return clarifier.ClarifierStructuredOutput(
            version="v1",
            type="stop",
            assistant_message="Thanks — I have enough to proceed.",
            reason="Enough context collected.",
            missing_fields=[],
            assumptions=[],
        )

    monkeypatch.setattr(clarifier, "call_llm_structured", fake_call_llm_structured)

    out = clarifier.run_clarifier(original_input="Build X", transcript=[], turn_count=2, force_stop=True)
    assert out.kind == "finalized"
    assert out.stop_reason == "Enough context collected."


def test_clarifier_engine_retry_then_error(monkeypatch) -> None:
    def fake_call_llm_structured(messages, schema, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(clarifier, "call_llm_structured", fake_call_llm_structured)

    try:
        clarifier.run_clarifier(original_input="Build X", transcript=[], turn_count=0, force_stop=False)
        assert False, "Expected exception"
    except RuntimeError:
        assert True


def test_build_enriched_prompt_pairs_and_stop_reason() -> None:
    enriched = clarifier.build_enriched_prompt(
        "Build X",
        [
            {"role": "assistant", "content": "What is your SLA?"},
            {"role": "user", "content": "99.9%"},
            {"role": "assistant", "content": "Any data residency requirements?"},
            {"role": "user", "content": "EU only"},
        ],
        stop_reason="Enough context collected.",
    )
    assert "Original request:" in enriched
    assert "Build X" in enriched
    assert "Clarifier Q/A:" in enriched
    assert "1) Q: What is your SLA?" in enriched
    assert "A: 99.9%" in enriched
    assert "2) Q: Any data residency requirements?" in enriched
    assert "A: EU only" in enriched
    assert "Stop reason:" in enriched
    assert "Enough context collected." in enriched


