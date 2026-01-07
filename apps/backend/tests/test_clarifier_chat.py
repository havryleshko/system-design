from __future__ import annotations

import types

import app.agent.system_design.clarifier as clarifier


def test_clarifier_engine_questions(monkeypatch) -> None:
    def fake_call_brain_json(messages, **kwargs):
        return {
            "version": "v1",
            "type": "questions",
            "assistant_message": "Q1?",
            "questions": [{"id": "q1", "text": "What is your SLA?", "priority": "blocking"}],
            "missing_fields": ["sla"],
            "assumptions": [],
        }

    monkeypatch.setattr(clarifier, "call_brain_json", fake_call_brain_json)

    out = clarifier.run_clarifier(original_input="Build X", transcript=[], turn_count=0, force_final=False)
    assert out.kind == "active"
    assert "Q1" in out.assistant_message


def test_clarifier_engine_final(monkeypatch) -> None:
    def fake_call_brain_json(messages, **kwargs):
        return {
            "version": "v1",
            "type": "final",
            "status": "ready",
            "assistant_message": "Done.",
            "final_summary": "Summary",
            "missing_fields": [],
            "assumptions": [],
            "enriched_prompt": "Prompt\n\nClarifier Summary:\nSummary",
        }

    monkeypatch.setattr(clarifier, "call_brain_json", fake_call_brain_json)

    out = clarifier.run_clarifier(original_input="Build X", transcript=[], turn_count=2, force_final=True)
    assert out.kind == "finalized"
    assert out.final_status == "ready"
    assert out.final_summary == "Summary"
    assert "Clarifier Summary" in (out.enriched_prompt or "")


def test_clarifier_engine_fallback_on_exception(monkeypatch) -> None:
    def fake_call_brain_json(messages, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(clarifier, "call_brain_json", fake_call_brain_json)

    out = clarifier.run_clarifier(original_input="Build X", transcript=[], turn_count=0, force_final=False)
    assert out.kind == "active"
    assert "deployment" in out.assistant_message.lower()


def test_clarifier_engine_fallback_on_invalid_payload(monkeypatch) -> None:
    def fake_call_brain_json(messages, **kwargs):
        # Missing required `assistant_message` should force validation failure and fallback.
        return {"type": "questions"}

    monkeypatch.setattr(clarifier, "call_brain_json", fake_call_brain_json)

    out = clarifier.run_clarifier(original_input="Build X", transcript=[], turn_count=0, force_final=False)
    assert out.kind == "active"
    # Should fall back to a safe concrete question
    assert "scale" in out.assistant_message.lower()


