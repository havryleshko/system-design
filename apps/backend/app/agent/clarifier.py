from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from app.agent.llm import call_llm_structured


MAX_TURNS = 5
MAX_MESSAGE_CHARS = 4_000
MAX_SESSION_CHARS = 40_000


class ClarifierQuestion(BaseModel):
    id: str
    text: str
    priority: Literal["blocking", "important", "optional"] = "important"
    suggested_answers: list[str] = Field(default_factory=list, min_length=3, max_length=4)


class ClarifierStructuredOutput(BaseModel):
    version: Literal["v1"] = "v1"
    type: Literal["question", "stop"]
    assistant_message: str
    question: Optional[ClarifierQuestion] = None
    reason: Optional[str] = None
    missing_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_by_type(self) -> "ClarifierStructuredOutput":
        if self.type == "question":
            if self.question is None:
                raise ValueError("question is required when type=question")
            return self
        if self.reason is None or not (self.reason or "").strip():
            raise ValueError("reason is required when type=stop")
        return self
		
@dataclass(frozen=True)
class ClarifierEngineResult:
    kind: Literal["active", "finalized"]
    assistant_message: str
    questions: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: Optional[str] = None
    missing_fields: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


def _system_prompt(*, force_stop: bool) -> str:
    return (
        "You are an intake clarifier for an agentic system design tool.\n"
        "Your job is to ask ONLY clarifying questions needed to design and implement the system.\n"
        "Rules:\n"
        "- Ask EXACTLY 1 question at a time.\n"
        "- Provide EXACTLY 3-4 suggested user answers (short, concrete).\n"
        "- The question should be the highest-impact missing info needed for a high-quality architecture blueprint.\n"
        "- Prefer concrete requirements (numbers, SLAs, constraints).\n"
        "- Avoid long explanations.\n"
        "- The assistant_message must be short.\n"
        "- You MAY return type=stop when you judge there is enough context collected to proceed.\n"
        "- Output MUST be valid JSON ONLY. No markdown.\n"
        "- JSON must match the structured schema.\n"
        + ("- You MUST return type=stop in this response.\n" if force_stop else "")
    )


def _truncate(s: str, max_chars: int) -> str:
    s = s or ""
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n…[truncated]"


def _cap_messages_for_context(messages: list[BaseMessage], max_total_chars: int) -> list[BaseMessage]:
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
    force_stop: bool,
) -> ClarifierEngineResult:
    if turn_count >= MAX_TURNS:
        force_stop = True

    original_input = _truncate(original_input.strip(), MAX_SESSION_CHARS)

    convo: list[BaseMessage] = []
    convo.append(SystemMessage(content=_system_prompt(force_stop=force_stop)))
    convo.append(HumanMessage(content=f"Original request:\n{original_input}"))

    for msg in transcript:
        role = str(msg.get("role") or "user")
        content = _truncate(str(msg.get("content") or ""), MAX_MESSAGE_CHARS)
        if not content.strip():
            continue
        convo.append(_to_lc_message(role, content))

    convo = _cap_messages_for_context(convo, MAX_SESSION_CHARS)

    payload = call_llm_structured(convo, ClarifierStructuredOutput, retries=2)

    if payload.type == "stop":
        return ClarifierEngineResult(
            kind="finalized",
            assistant_message=payload.assistant_message,
            questions=[],
            stop_reason=payload.reason,
            missing_fields=payload.missing_fields,
            assumptions=payload.assumptions,
        )

    qd = (payload.question or ClarifierQuestion(id="q", text=payload.assistant_message, suggested_answers=[])).model_dump()
    assistant_message = (payload.assistant_message or "").strip() or str(qd.get("text") or "")
    return ClarifierEngineResult(
        kind="active",
        assistant_message=assistant_message,
        questions=[qd],
        missing_fields=payload.missing_fields,
        assumptions=payload.assumptions,
    )


def build_enriched_prompt(
    original_input: str,
    transcript: list[dict[str, Any]],
    *,
    stop_reason: str | None = None,
) -> str:
    original = (original_input or "").strip()
    lines: list[str] = []
    lines.append("Original request:")
    lines.append(original)
    lines.append("")
    lines.append("Clarifier Q/A:")

    qa_pairs: list[tuple[str, str]] = []
    pending_q: str | None = None
    pending_a: list[str] = []

    for msg in (transcript or []):
        role = str(msg.get("role") or "").lower()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue

        if role == "assistant":
            if pending_q is not None:
                qa_pairs.append((pending_q, "\n".join(pending_a).strip()))
            pending_q = content
            pending_a = []
            continue

        if role == "user":
            if pending_q is None:
                continue
            pending_a.append(content)
            continue

    if pending_q is not None:
        qa_pairs.append((pending_q, "\n".join(pending_a).strip()))

    if not qa_pairs:
        lines.append("(none)")
    else:
        for i, (q, a) in enumerate(qa_pairs, start=1):
            lines.append(f"{i}) Q: {q}")
            lines.append(f"   A: {a if a else '(no answer)'}")

    if stop_reason and stop_reason.strip():
        lines.append("")
        lines.append("Stop reason:")
        lines.append(stop_reason.strip())

    return "\n".join(lines).strip() + "\n"

