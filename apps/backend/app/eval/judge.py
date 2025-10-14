"""LLM-based grading utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict

try:  # pragma: no cover - optional dependency guarded in runtime
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
except ImportError:  # pragma: no cover
    ChatOpenAI = None  # type: ignore[assignment]
    SystemMessage = None  # type: ignore[assignment]
    HumanMessage = None  # type: ignore[assignment]


@dataclass(slots=True)
class Judgement:
    score: float
    passed: bool
    feedback: str


class LLMJudge:
    """Simple LLM-as-judge scored evaluation."""

    def __init__(self, model: str | None = None, threshold: float = 0.6):
        self.model_name = model or "gpt-4o-mini"
        self.threshold = threshold

    @lru_cache(maxsize=2)
    def _llm(self):
        if ChatOpenAI is None:
            raise RuntimeError("langchain-openai is not installed. Install backend requirements.")
        return ChatOpenAI(model=self.model_name, temperature=0.0)


    @staticmethod
    def _parse_response(raw_text: str) -> Dict[str, object]:
        text = (raw_text or "").strip()
        if text.startswith("```"):
            # Drop optional fence language hint and closing fence
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
            if text.endswith("```"):
                text = text[: -3]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = text[start : end + 1]
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError as exc:  # pragma: no cover - rare formatting
                    raise RuntimeError(f"Judge returned malformed JSON: {raw_text}") from exc
            raise RuntimeError(f"Judge returned malformed JSON: {raw_text}")

    def judge(self, prompt: str, output: str, criteria: str) -> Judgement:
        if SystemMessage is None or HumanMessage is None:
            raise RuntimeError("langchain-core is not installed. Install backend requirements.")

        system = SystemMessage(
            content=(
                "You are a meticulous senior system design reviewer. "
                "Provide a score between 0 and 1 and short feedback JSON."
                "Return JSON with keys score (0-1) and feedback (string)."
            )
        )
        human_payload: Dict[str, str] = {
            "task_prompt": prompt,
            "agent_output": output,
            "success_criteria": criteria,
        }
        human = HumanMessage(content=json.dumps(human_payload, ensure_ascii=False))

        raw = self._llm().invoke([system, human])
        try:
            data = self._parse_response(raw.content)
        except RuntimeError as exc:  # pragma: no cover - LLM fallback
            raise RuntimeError(str(exc)) from exc

        score = float(data.get("score", 0.0))
        score = max(0.0, min(1.0, score))
        feedback = str(data.get("feedback") or "").strip()
        passed = score >= self.threshold
        return Judgement(score=score, passed=passed, feedback=feedback)


