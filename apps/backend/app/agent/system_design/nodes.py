from typing import Any, Dict, Optional, Sequence
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from .state import State
from langchain_openai import ChatOpenAI
from functools import lru_cache
import json, os, math
from datetime import datetime
from langgraph.types import interrupt, Command
import logging
try:
    from app.storage.memory import add_event, record_node_tokens
except ImportError:
    from app.storage.memory import add_event

    def record_node_tokens(
        run_id: str,
        node: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
            return None
from app.schemas.runs import RunEvent
from app.services.langgraph_store import (
    load_long_term_messages,
    record_long_term_memory,
    search_semantic_memory,
)
logger = logging.getLogger(__name__)


def _coerce_str(value: Any, *, max_len: Optional[int] = None) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        text = str(value)
    elif isinstance(value, str):
        text = value
    else:
        text = str(value)
    text = text.strip()
    if not text:
        return None
    if max_len is not None and len(text) > max_len:
        text = text[:max_len].rstrip()
    return text or None


def _coerce_str_list(
    value: Any,
    *,
    max_items: int = 4,
    max_len: int = 120,
) -> list[str]:
    items: list[str] = []
    if value is None:
        return items
    if isinstance(value, (int, float, str)):
        text = _coerce_str(value, max_len=max_len)
        return [text] if text else items
    if isinstance(value, Sequence):
        seen: set[str] = set()
        for entry in value:
            text = _coerce_str(entry, max_len=max_len)
            if not text or text in seen:
                continue
            items.append(text)
            seen.add(text)
            if len(items) >= max_items:
                break
    return items


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n", ""}:
            return False
    return bool(value)


def _compute_plan_quality(scope: dict[str, Any] | None, steps: Sequence[dict[str, Any]] | None) -> float:
    scope = scope or {}
    risks = len(scope.get("risks") or [])
    blocking = len(scope.get("blocking_issues") or [])
    info = len(scope.get("info_issues") or [])
    step_count = len(steps or [])

    # Simple heuristic: more steps and fewer risks/issues raise the score.
    base = 0.4 + 0.08 * min(step_count, 5)
    penalty = 0.15 * blocking + 0.1 * info + 0.08 * risks
    quality = base - penalty
    if scope.get("needs_clarifier"):
        quality -= 0.2
    return max(0.0, min(1.0, quality))


def _clarifier_answer_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return "\n".join(_clarifier_answer_to_text(item) for item in value if item is not None).strip()
    if isinstance(value, dict):
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    coerced = _coerce_str(value)
    return coerced or ""


def _match_enum(value: Optional[str], options: Sequence[str], default: str) -> str:
    if value:
        for opt in options:
            if value.lower() == opt.lower():
                return opt
    return default


def _normalise_tags(raw: Any, *, limit: int = 6, max_len: int = 40) -> list[str]:
    tags: list[str] = []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return tags
    for item in raw:
        tag = _coerce_str(item, max_len=max_len)
        if not tag:
            continue
        if tag in tags:
            continue
        tags.append(tag)
        if len(tags) >= limit:
            break
    return tags


def _strip_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_nulls(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_nulls(item) for item in value if item is not None]
    return value


def _fallback_architecture(goal: str, design_brief: str) -> Dict[str, Any]:
    label = _coerce_str(goal, max_len=80) or "Proposed System"
    element: Dict[str, Any] = {"id": "system", "kind": "System", "label": label}
    description = _coerce_str(design_brief, max_len=280)
    if description:
        element["description"] = description
    return {
        "elements": [element],
        "relations": [],
    }


def normalise_architecture(raw: Any, *, goal: str, design_brief: str) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    elements: list[dict[str, Any]] = []
    for item in data.get("elements", []) if isinstance(data.get("elements"), list) else []:
        if not isinstance(item, dict):
            continue
        element_id = _coerce_str(item.get("id"), max_len=64)
        label = _coerce_str(item.get("label"), max_len=80)
        kind = _coerce_str(item.get("kind"), max_len=32) or "Component"
        if not element_id or not label:
            continue
        element: Dict[str, Any] = {"id": element_id, "kind": kind, "label": label}
        description = _coerce_str(item.get("description"), max_len=280)
        if description:
            element["description"] = description
        technology = _coerce_str(item.get("technology"), max_len=80)
        if technology:
            element["technology"] = technology
        parent = _coerce_str(item.get("parent"), max_len=64)
        if parent:
            element["parent"] = parent
        tags = _normalise_tags(item.get("tags"))
        if tags:
            element["tags"] = tags
        elements.append(element)

    relations: list[dict[str, Any]] = []
    for rel in data.get("relations", []) if isinstance(data.get("relations"), list) else []:
        if not isinstance(rel, dict):
            continue
        source = _coerce_str(rel.get("source"), max_len=64)
        target = _coerce_str(rel.get("target"), max_len=64)
        label = _coerce_str(rel.get("label"), max_len=120)
        if not source or not target or not label:
            continue
        entry: Dict[str, Any] = {"source": source, "target": target, "label": label}
        technology = _coerce_str(rel.get("technology"), max_len=80)
        if technology:
            entry["technology"] = technology
        direction = _coerce_str(rel.get("direction"))
        if direction:
            entry["direction"] = _match_enum(direction, ["->", "<-", "<->"], "->")
        relations.append(entry)

    groups: list[dict[str, Any]] = []
    for group in data.get("groups", []) if isinstance(data.get("groups"), list) else []:
        if not isinstance(group, dict):
            continue
        group_id = _coerce_str(group.get("id"), max_len=64)
        label = _coerce_str(group.get("label"), max_len=80)
        kind = _coerce_str(group.get("kind"), max_len=32) or "SystemBoundary"
        children_raw = group.get("children")
        if not group_id or not label or not isinstance(children_raw, list):
            continue
        children: list[str] = []
        for child in children_raw:
            child_id = _coerce_str(child, max_len=64)
            if not child_id:
                continue
            if child_id not in children:
                children.append(child_id)
        if not children:
            continue
        entry: Dict[str, Any] = {"id": group_id, "kind": kind, "label": label, "children": children[:32]}
        technology = _coerce_str(group.get("technology"), max_len=80)
        if technology:
            entry["technology"] = technology
        groups.append(entry)

    notes = _coerce_str(data.get("notes"), max_len=400)

    if not elements:
        return _fallback_architecture(goal, design_brief)

    arch: Dict[str, Any] = {
        "elements": elements,
        "relations": relations,
    }
    if groups:
        arch["groups"] = groups
    if notes:
        arch["notes"] = notes
    return arch

@lru_cache(maxsize=4)
def make_brain(model: str | None = None) -> ChatOpenAI:
    model_name = model or os.getenv("CHAT_OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model_name)

def to_message(x: any) -> BaseMessage:
    if isinstance(x, BaseMessage):
        return x
    if isinstance(x, str):
        return HumanMessage(content=x)
    if isinstance(x, dict):
        role = (x.get("role") or "user").lower()
        content = x.get("content", "")
        return HumanMessage(content=content) if role in ("user", "human") else AIMessage(content=content)
    return HumanMessage(content=str(x))

def normalise(ms: Optional[list[any]]) -> list[BaseMessage]:
    return [to_message(m) for m in (ms or [])]

def get_content(m: any) -> str:
    return getattr(m, "content", m.get("content", "") if isinstance(m, dict) else str(m))

def last_human_text(messages: list[any]) -> str:
    ms = normalise(messages)
    text = ""
    for m in ms:
        if isinstance(m, HumanMessage):
            text = str(m.content or "")
        else:
            if isinstance(m, dict) and (m.get("role") or "user").lower() in ("user", "human"):
                text = str(m.get("content", "") or "")
    return text.strip()


def _latest_human_message(messages: list[any]) -> Optional[HumanMessage]:
    for msg in reversed(normalise(messages)):
        if isinstance(msg, HumanMessage):
            return msg
        if isinstance(msg, dict):
            role = (msg.get("role") or "user").lower()
            if role in ("user", "human"):
                content = _coerce_str(msg.get("content"))
                if content:
                    return HumanMessage(content=content)
    return None


def json_only(text: str) -> Optional[dict]:
    try:
        json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            return json.loads(snippet)
        except Exception:
            return None
    return None

def call_brain(
    messages: list[any],
    *,
    state: Optional[State] = None,
    run_id: str | None = None,
    node: str | None = None,
) -> str:
    original_ms = normalise(messages)
    prompt_msg: Optional[BaseMessage] = None
    for candidate in reversed(original_ms):
        if isinstance(candidate, HumanMessage):
            prompt_msg = candidate
            break

    sys_m = [m for m in original_ms if isinstance(m, SystemMessage)]
    other_m = [m for m in original_ms if not isinstance(m, SystemMessage)]
    recent: list[BaseMessage] = []
    if state is not None:
        state_messages = state.get("messages", []) or []
        if state_messages:
            recent = normalise(state_messages[-15:])

    metadata: Dict[str, Any] = {}
    if state is not None:
        metadata = state.get("metadata", {}) or {}
    user_id = metadata.get("user_id")
    thread_id = metadata.get("thread_id")
    process_id = thread_id or run_id or metadata.get("run_id")

    # Hybrid memory: episodic (recent) + semantic (relevant)
    episodic_messages = load_long_term_messages(
        user_id=user_id,
        process_id=process_id,
        limit=12,
    )
    
    # Extract query from current prompt for semantic search
    semantic_messages: list[BaseMessage] = []
    if prompt_msg and user_id:
        query_text = get_content(prompt_msg)
        if query_text and len(query_text.strip()) > 10:  # Only search if query is substantial
            try:
                semantic_messages = search_semantic_memory(
                    user_id=user_id,
                    query=query_text,
                    limit=10,
                )
            except Exception as exc:
                logger.warning("Semantic search failed, using episodic only: %s", exc)
    
    # Merge episodic and semantic, deduplicating by content
    memory_messages: list[BaseMessage] = []
    seen_content: set[str] = set()
    
    # Add episodic first (preserves chronological order)
    for msg in episodic_messages:
        content = get_content(msg)
        if content and content not in seen_content:
            seen_content.add(content)
            memory_messages.append(msg)
    
    # Add semantic results (most relevant first)
    for msg in semantic_messages:
        content = get_content(msg)
        if content and content not in seen_content:
            seen_content.add(content)
            memory_messages.append(msg)

    if memory_messages:
        ms = sys_m + memory_messages + recent + other_m
    elif recent:
        ms = sys_m + recent + other_m
    else:
        ms = sys_m + other_m

    brain = make_brain()
    r = brain.invoke(ms)
    record_long_term_memory(
        user_id=user_id,
        process_id=process_id,
        prompt=prompt_msg,
        response=r,
        run_id=run_id,
        node=node,
    )
    if run_id and node:
        log_token_usage(run_id, node, r)
    return getattr(r, "content", "") or ""


def call_brain_json(
    messages: list[any],
    *,
    state: Optional[State] = None,
    run_id: str | None = None,
    node: str | None = None,
) -> dict:
    raw = call_brain(messages, state=state, run_id=run_id, node=node)
    try:
        return json.loads(raw)
    except Exception:
        data = json_only(raw)
        if data is None:
            raise ValueError("LLM response was not valid JSON")
        return data


def log_token_usage(run_id: str, node: str, response: BaseMessage) -> None:
    usage = getattr(response, "usage_metadata", None) or {}
    prompt_tokens = int(usage.get("input_tokens", 0))
    completion_tokens = int(usage.get("output_tokens", 0))
    total = int(usage.get("total_tokens", prompt_tokens + completion_tokens))
    ts_ms = int(datetime.now().timestamp() * 1000)
    add_event(run_id, RunEvent(
        ts_ms=ts_ms,
        level="info",
        message=f"{node} tokens",
        data={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total,
        }
    ))
    record_node_tokens(run_id, node, prompt_tokens, completion_tokens, total)



def estimate_tokens(text: str) -> int:
    words = text.split()
    return max(1, math.ceil(len(words) / 0.75))


def trim_snippet(text: str, max_chars: int = 320) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"




def orchestrator(state: State) -> Dict[str, any]:
    updates: Dict[str, any] = {}
    orchestrator_state = dict(state.get("orchestrator") or {})

    phase = (state.get("run_phase") or "planner").lower()
    updates.setdefault("run_phase", phase)

    plan_scope = state.get("plan_scope") or {}
    if phase == "planner" and plan_scope.get("needs_clarifier"):
        blocking = plan_scope.get("blocking_issues") or []
        question_lines = ["I need a bit more detail before planning:"]
        if blocking:
            question_lines.extend(f"- {item}" for item in blocking)
        question_lines.append("Please clarify the missing information.")
        payload = {
            "type": "clarifier",
            "question": "\n".join(question_lines),
            "issues": blocking,
        }
        answer = interrupt(payload)
        answer_text = _clarifier_answer_to_text(answer)
        if answer_text:
            updates["messages"] = [HumanMessage(content=answer_text)]
        updates["plan_scope"] = {}
        updates["run_phase"] = "planner"
        orchestrator_state["last_phase"] = "planner_clarifier"
        updates["orchestrator"] = orchestrator_state
        return updates

    orchestrator_state["last_phase"] = phase
    updates["orchestrator"] = orchestrator_state
    return updates



def planner_agent(state: State) -> Command | Dict[str, any]:
    plan_scope = state.get("plan_scope") or {}
    plan_state = state.get("plan_state") or {}

    if plan_scope.get("status") != "completed":
        return Command(goto="planner_scope")

    if plan_state.get("status") != "completed":
        return Command(goto="planner_steps")

    if plan_scope.get("needs_clarifier"):
        # Wait for orchestrator to trigger clarifier before moving forward
        return {"plan_state": {}, "run_phase": "planner"}

    metadata = state.get("metadata") or {}
    quality_raw = plan_state.get("quality")
    quality: Optional[float] = None
    if quality_raw is not None:
        try:
            quality = float(quality_raw)
        except (TypeError, ValueError):
            quality = None

    if quality is not None:
        min_quality = 0.5
        already_retried = metadata.get("planner_quality_retry")
        if quality < min_quality and not already_retried:
            updated_meta = dict(metadata)
            updated_meta["planner_quality_retry"] = True
            return {
                "plan_state": {},
                "metadata": updated_meta,
                "run_phase": "planner",
            }

    summary = _coerce_str(plan_state.get("summary"), max_len=600)
    updates: Dict[str, Any] = {"run_phase": "research"}
    if summary:
        updates["plan"] = summary
    if quality is not None:
        updates["plan_quality"] = quality
    _record_final_plan_memory(state, summary)
    return updates


def _record_final_plan_memory(state: State, summary: Optional[str]) -> None:
    metadata = state.get("metadata") or {}
    user_id = metadata.get("user_id")
    thread_id = metadata.get("thread_id")
    run_id = metadata.get("run_id")
    process_id = thread_id or run_id
    if not (user_id and process_id):
        return

    prompt_msg = _latest_human_message(state.get("messages", []))
    if prompt_msg is None:
        return

    plan_state = state.get("plan_state") or {}
    steps = plan_state.get("steps") or []
    lines: list[str] = []
    summary_text = _coerce_str(summary, max_len=600)
    if summary_text:
        lines.append(f"Summary: {summary_text}")
    for step in steps:
        if not isinstance(step, dict):
            continue
        title = _coerce_str(step.get("title"), max_len=120)
        detail = _coerce_str(step.get("detail"), max_len=240)
        if title and detail:
            lines.append(f"{title}: {detail}")
        elif title:
            lines.append(title)
        elif detail:
            lines.append(detail)

    if not lines:
        return

    response_msg = AIMessage(content="\n".join(lines))
    try:
        record_long_term_memory(
            user_id=user_id,
            process_id=process_id,
            prompt=prompt_msg,
            response=response_msg,
            run_id=run_id,
            node="planner_agent",
        )
    except Exception as exc:
        logger.warning("planner_agent memory write failed: %s", exc)


def planner_scope(state: State) -> Dict[str, any]:
    goal = _coerce_str(state.get("goal"), max_len=400) or ""
    latest_user = _coerce_str(last_human_text(state.get("messages", [])), max_len=400) or ""
    metadata = state.get("metadata") or {}
    user_id = metadata.get("user_id")
    memory_highlights: list[str] = []
    if user_id and goal:
        try:
            matches = search_semantic_memory(user_id=user_id, query=goal, limit=3)
            for msg in matches:
                content = getattr(msg, "content", "")
                text = _coerce_str(content, max_len=200)
                if text:
                    memory_highlights.append(text)
        except Exception as exc:
            logger.warning("planner_scope semantic search failed: %s", exc)

    info_issues: list[str] = []
    blocking_issues: list[str] = []
    if not goal:
        blocking_issues.append("Goal is missing or empty.")
    elif len(goal.split()) < 6:
        info_issues.append("Goal lacks detail; describe users, scale, or success metrics.")
    if not latest_user or latest_user.lower() == goal.lower():
        info_issues.append("Constraints or requirements not provided.")

    needs_clarifier = bool(blocking_issues)
    risks = [(issue or "").strip()[:120] for issue in (blocking_issues + info_issues) if (issue or "").strip()]
    plan_scope = {
        "goal": goal,
        "latest_input": latest_user,
        "memory_highlights": memory_highlights,
        "info_issues": info_issues,
        "blocking_issues": blocking_issues,
        "needs_clarifier": needs_clarifier,
        "needs_follow_up": bool(info_issues or blocking_issues),
        "issues": blocking_issues + info_issues,
        "risks": risks[:5],
        "status": "completed",
    }
    return {"plan_scope": plan_scope}


def planner_steps(state: State) -> Dict[str, any]:
    scope = state.get("plan_scope") or {}
    goal = _coerce_str(scope.get("goal"), max_len=400) or _coerce_str(state.get("goal"), max_len=400) or ""
    additional = _coerce_str(scope.get("latest_input"), max_len=400) or ""
    highlights = scope.get("memory_highlights") or []
    issues = scope.get("issues") or []
    scope_risks = scope.get("risks") or []

    schema_desc = json.dumps(
        {
            "steps": [
                {
                    "id": "plan-1",
                    "title": "short title",
                    "detail": "1 sentence detail",
                    "inputs": ["existing asset", "key constraint"],
                    "outputs": ["artifact or milestone"],
                    "depends_on": ["plan-0"],
                    "owner": "team or role",
                    "needs_research": False,
                    "needs_cost": False,
                }
            ],
            "summary": "2-3 sentence summary",
            "risks": ["short risk"],
        },
        ensure_ascii=False,
    )
    sys = SystemMessage(content=(
        "You are a senior system design planner. Return JSON only matching this schema:\n"
        f"{schema_desc}\n"
        "Keep at most 5 concise steps. Each detail is one short sentence. "
        "Optional per-step metadata: inputs/outputs/depends_on arrays of short strings, an owner string, "
        "and needs_research / needs_cost booleans. "
        "If you see notable risks, add a top-level `risks` array of short plain-language statements. "
        "If there are outstanding issues, include a TODO-style step describing what must be clarified."
    ))
    lines = [f"Goal:\n{goal or 'Unknown'}"]
    if additional:
        lines.append(f"\nConstraints or recent input:\n{additional}")
    if highlights:
        lines.append("\nContext snippets:\n" + "\n".join(f"- {h}" for h in highlights))
    if issues:
        lines.append("\nOutstanding issues:\n" + "\n".join(f"- {issue}" for issue in issues))
    prompt = "\n".join(lines)

    run_id = state.get("metadata", {}).get("run_id")
    raw = call_brain(
        [sys, HumanMessage(content=prompt)],
        state=state,
        run_id=run_id,
        node="planner_steps",
    )
    parsed = json_only(raw) or {}
    steps = parsed.get("steps")
    summary = parsed.get("summary")
    llm_risks = _coerce_str_list(parsed.get("risks"), max_items=5, max_len=120)
    risks = _coerce_str_list(scope_risks, max_items=5, max_len=120)
    for risk in llm_risks:
        if risk not in risks:
            risks.append(risk)
    if not isinstance(steps, list) or not steps:
        fallback_detail = goal or "Clarify the desired system outcome with the user."
        normalized_steps = [
            {
                "id": "plan-1",
                "title": "Outline high-level approach",
                "detail": fallback_detail[:240] or "Draft initial plan",
            }
        ]
        if issues:
            todo_detail = "; ".join(issues)[:240]
            normalized_steps.insert(
                0,
                {
                    "id": "plan-todo",
                    "title": "Clarify missing requirements",
                    "detail": f"TODO: {todo_detail}",
                },
            )
        normalized_steps = normalized_steps[:5]
        quality = _compute_plan_quality(scope, normalized_steps)
        summary_text = "\n".join(f"- {step['title']}" for step in normalized_steps)
        return {
            "plan": summary_text,
            "plan_state": {
                "status": "completed",
                "steps": normalized_steps,
                "summary": summary_text,
                "issues": issues,
                "risks": risks,
                "quality": quality,
            },
        }

    normalized_steps = []
    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        title = _coerce_str(step.get("title"), max_len=120) or f"Step {idx}"
        detail = _coerce_str(step.get("detail"), max_len=240) or title
        step_id = _coerce_str(step.get("id"), max_len=32) or f"plan-{idx}"
        entry: Dict[str, Any] = {
            "id": step_id,
            "title": title,
            "detail": detail,
            "needs_research": _coerce_bool(step.get("needs_research")),
            "needs_cost": _coerce_bool(step.get("needs_cost")),
        }
        owner = _coerce_str(step.get("owner"), max_len=80)
        if owner:
            entry["owner"] = owner
        inputs = _coerce_str_list(step.get("inputs"), max_items=4, max_len=80)
        if inputs:
            entry["inputs"] = inputs
        outputs = _coerce_str_list(step.get("outputs"), max_items=4, max_len=80)
        if outputs:
            entry["outputs"] = outputs
        depends_on = _coerce_str_list(step.get("depends_on"), max_items=5, max_len=32)
        if depends_on:
            entry["depends_on"] = depends_on
        normalized_steps.append(
            entry
        )

    if issues:
        todo_detail = "; ".join(issues)[:240]
        normalized_steps.insert(
            0,
            {
                "id": "plan-todo",
                "title": "Clarify missing requirements",
                "detail": f"TODO: {todo_detail}",
            },
        )

    normalized_steps = normalized_steps[:5]
    quality = _compute_plan_quality(scope, normalized_steps)
    summary_text = _coerce_str(summary, max_len=600) or "\n".join(
        f"- {step['title']}" for step in normalized_steps
    )

    return {
        "plan": summary_text,
        "plan_state": {
            "status": "completed",
            "steps": normalized_steps,
            "summary": summary_text,
            "issues": issues,
            "risks": risks,
            "quality": quality,
        },
    }


def research_agent(state: State) -> Dict[str, any]:
    """Placeholder research agent."""
    return {
        "research_state": {
            "status": "pending",
            "notes": "Research agent not yet implemented.",
        },
        "run_phase": "design",
    }


def design_agent(state: State) -> Dict[str, any]:
    """Placeholder design agent."""
    return {
        "design_state": {
            "status": "pending",
            "notes": "Design agent not yet implemented.",
        },
        "run_phase": "critic",
    }


def critic_agent(state: State) -> Dict[str, any]:
    """Placeholder critic agent."""
    return {
        "critic_state": {
            "status": "pending",
            "notes": "Critic agent not yet implemented.",
            "next_phase": "evals",
        },
        "run_phase": "evals",
    }


def evals_agent(state: State) -> Dict[str, any]:
    """Placeholder evals agent."""
    return {
        "eval_state": {
            "status": "pending",
            "notes": "Evals agent not yet implemented.",
        },
        "run_phase": "done",
    }
