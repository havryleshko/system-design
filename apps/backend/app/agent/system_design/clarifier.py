from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage

from app.agent.system_design.nodes import call_brain_json


MAX_TURNS = 8
MAX_MESSAGE_CHARS = 4_000
MAX_SESSION_CHARS = 40_000


class ClarifierQuestion(BaseModel):
    id: str
    text: str
    priority: Literal["blocking", "important", "optional"] = "important"


class ClarifierQuestionsPayload(BaseModel):
    version: Literal["v1"] = "v1"
    type: Literal["questions"] = "questions"
    assistant_message: str
    questions: list[ClarifierQuestion] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ClarifierFinalPayload(BaseModel):
    version: Literal["v1"] = "v1"
    type: Literal["final"] = "final"
    status: Literal["ready", "draft"] = "draft"
    assistant_message: str
    final_summary: str
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    enriched_prompt: str


ClarifierLLMOutput = ClarifierQuestionsPayload | ClarifierFinalPayload


@dataclass(frozen=True)
class ClarifierEngineResult:
    kind: Literal["active", "finalized"]
    assistant_message: str
    final_status: Optional[Literal["ready", "draft"]] = None
    final_summary: Optional[str] = None
    enriched_prompt: Optional[str] = None
    missing_fields: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


def _system_prompt(*, force_final: bool) -> str:
    return (
        "You are an intake clarifier for an agentic system design tool.\n"
        "Your job is to ask ONLY clarifying questions needed to design and implement the system.\n"
        "Rules:\n"
        "- Ask 1-3 questions at a time.\n"
        "- Prefer concrete requirements (numbers, SLAs, constraints).\n"
        "- Avoid long explanations.\n"
        "- Output MUST be valid JSON ONLY. No markdown.\n"
        "- JSON must match one of these shapes:\n"
        "  (A) Questions:\n"
        "    {\"version\":\"v1\",\"type\":\"questions\",\"assistant_message\":\"...\",\"questions\":[{\"id\":\"...\",\"text\":\"...\",\"priority\":\"blocking|important|optional\"}],\"missing_fields\":[...],\"assumptions\":[...]}\n"
        "  (B) Final:\n"
        "    {\"version\":\"v1\",\"type\":\"final\",\"status\":\"ready|draft\",\"assistant_message\":\"...\",\"final_summary\":\"...\",\"missing_fields\":[...],\"assumptions\":[...],\"enriched_prompt\":\"...\"}\n"
        + ("- You MUST return type=final in this response.\n" if force_final else "")
    )


def _truncate(s: str, max_chars: int) -> str:
    s = s or ""
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n…[truncated]"


def _cap_messages_for_context(messages: list[BaseMessage], max_total_chars: int) -> list[BaseMessage]:
    # Keep the most recent messages within a rough char budget.
    kept: list[BaseMessage] = []
    total = 0
    for m in reversed(messages):
        content = getattr(m, "content", "") or ""
        total += len(str(content))
        if total > max_total_chars:
            break
        kept.append(m)
    return list(reversed(kept))


def _to_lc_message(role: str, content: str) -> BaseMessage:
    role_l = (role or "user").lower()
    if role_l == "assistant":
        return AIMessage(content=content)
    if role_l == "system":
        return SystemMessage(content=content)
    return HumanMessage(content=content)


def run_clarifier(
    *,
    original_input: str,
    transcript: list[dict[str, Any]],
    turn_count: int,
    force_final: bool,
) -> ClarifierEngineResult:
    # Enforce max turns by forcing final output.
    if turn_count >= MAX_TURNS:
        force_final = True

    original_input = _truncate(original_input.strip(), MAX_SESSION_CHARS)

    convo: list[BaseMessage] = []
    convo.append(SystemMessage(content=_system_prompt(force_final=force_final)))
    convo.append(HumanMessage(content=f"Original request:\n{original_input}"))

    for msg in transcript:
        role = str(msg.get("role") or "user")
        content = _truncate(str(msg.get("content") or ""), MAX_MESSAGE_CHARS)
        if not content.strip():
            continue
        convo.append(_to_lc_message(role, content))

    convo = _cap_messages_for_context(convo, MAX_SESSION_CHARS)

    try:
        raw = call_brain_json(convo, state=None, run_id=None, node="clarifier")
    except Exception:
        # Safe fallback: one concrete question.
        return ClarifierEngineResult(
            kind="active",
            assistant_message="What is the target deployment environment (cloud provider/region, or on-prem)?",
            missing_fields=[],
            assumptions=[],
        )

    try:
        if raw.get("type") == "final":
            parsed = ClarifierFinalPayload.model_validate(raw)
            return ClarifierEngineResult(
                kind="finalized",
                assistant_message=parsed.assistant_message,
                final_status=parsed.status,
                final_summary=parsed.final_summary,
                enriched_prompt=parsed.enriched_prompt,
                missing_fields=parsed.missing_fields,
                assumptions=parsed.assumptions,
            )
        parsed = ClarifierQuestionsPayload.model_validate(raw)
        return ClarifierEngineResult(
            kind="active",
            assistant_message=parsed.assistant_message,
            missing_fields=parsed.missing_fields,
            assumptions=parsed.assumptions,
        )
    except ValidationError:
        return ClarifierEngineResult(
            kind="active",
            assistant_message="What scale should we design for (users, requests/sec, and data volume)?",
            missing_fields=[],
            assumptions=[],
        )


