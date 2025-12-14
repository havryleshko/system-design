from typing import Any, Dict, Optional, Sequence
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from .state import State
from langchain_openai import ChatOpenAI

from functools import lru_cache
import json, os, math
from datetime import datetime

from langgraph.types import interrupt, Command
import logging
import requests

# Supabase client is optional; guard import so graph can load without the package present.
try:
    from supabase import create_client  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    create_client = None

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
try:
    from app.services.langgraph_store import (
        load_long_term_messages,
        record_long_term_memory,
        search_semantic_memory,
    )
except ImportError: 
    def load_long_term_messages(*args, **kwargs):  #
        return []

    def record_long_term_memory(*args, **kwargs):
        return None

    def search_semantic_memory(*args, **kwargs):
        return []
logger = logging.getLogger(__name__)

TAVILY_ENDPOINT = "https://api.tavily.com/search"


@lru_cache(maxsize=1)
def _get_supabase_client() -> Any:
    if create_client is None:
        return None
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as exc: 
        logger.warning("Supabase client init failed: %s", exc)
        return None


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


def _compute_plan_quality(scope: dict[str, Any] | None, steps: Sequence[dict[str, Any]] | None, state: Optional[State] = None) -> float:
    scope = scope or {}
    steps = steps or []
    step_summaries: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        title = _coerce_str(step.get("title"), max_len=120) or ""
        detail = _coerce_str(step.get("detail"), max_len=240) or ""
        if title or detail:
            step_summaries.append(f"- {title}: {detail}" if title and detail else f"- {title or detail}")
    
    plan_text = "\n".join(step_summaries) if step_summaries else "No plan steps provided"
    
    # Schema for LLM response
    schema_desc = json.dumps(
        {
            "quality": 0.8,
            "notes": "Brief rationale for the quality score",
        },
        ensure_ascii=False,
    )
    
    sys = SystemMessage(content=(
        "You are a senior system design planner evaluating plan quality. "
        "Return JSON only matching this schema:\n"
        f"{schema_desc}\n"
        "Score quality from 0.0 to 1.0 based on: clarity of steps, coverage of requirements, "
        "presence of risks/issues, dependencies, and overall feasibility. "
        "Higher scores indicate clearer, more complete plans with fewer blockers."
    ))
    
    # Build prompt with context
    prompt_lines: list[str] = []
    if plan_text:
        prompt_lines.append(f"Plan steps:\n{plan_text}")
    
    issues = scope.get("issues") or []
    if issues:
        prompt_lines.append("\nKnown issues:\n" + "\n".join(f"- {_coerce_str(i, max_len=200)}" for i in issues if i))
    
    risks = scope.get("risks") or []
    if risks:
        prompt_lines.append("\nKnown risks:\n" + "\n".join(f"- {_coerce_str(r, max_len=200)}" for r in risks if r))
    
    blocking = scope.get("blocking_issues") or []
    if blocking:
        prompt_lines.append("\nBlocking issues:\n" + "\n".join(f"- {_coerce_str(b, max_len=200)}" for b in blocking if b))
    
    if scope.get("needs_clarifier"):
        prompt_lines.append("\nNote: Plan requires clarifier input before proceeding.")
    
    prompt = "\n".join(prompt_lines) if prompt_lines else "No plan context provided."
    
    run_id = state.get("metadata", {}).get("run_id") if state else None
    
    try:
        raw = call_brain(
            [sys, HumanMessage(content=prompt)],
            state=state,
            run_id=run_id,
            node="planner_quality",
        )
        parsed = json_only(raw) or {}
        quality_val = parsed.get("quality")
        
        if quality_val is not None:
            try:
                quality_float = float(quality_val)
                return max(0.0, min(1.0, quality_float))
            except (TypeError, ValueError):
                logger.warning("_compute_plan_quality: invalid quality value: %s", quality_val)
                return 0.0
        else:
            logger.warning("_compute_plan_quality: LLM response missing quality field")
            return 0.0
    except Exception as exc:
        logger.warning("_compute_plan_quality: LLM call failed: %s", exc)
        return 0.0


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


def _limit_strings(items: list[str], *, limit: int = 8) -> list[str]:
    seen: set[str] = set()
    trimmed: list[str] = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        trimmed.append(item)
        seen.add(item)
        if len(trimmed) >= limit:
            break
    return trimmed


def _limit_dicts(items: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    trimmed: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = tuple(sorted(f"{k}:{item.get(k)}" for k in item.keys()))
        if key in seen:
            continue
        trimmed.append(item)
        seen.add(key)
        if len(trimmed) >= limit:
            break
    return trimmed


def _research_payload(
    source: str,
    status: str,
    *,
    highlights: Optional[list[str]] = None,
    citations: Optional[list[dict[str, Any]]] = None,
    risks: Optional[list[str]] = None,
    notes: Optional[str] = None,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": source,
        "status": status,
        "highlights": highlights or [],
        "citations": citations or [],
        "risks": risks or [],
    }
    if notes:
        payload["notes"] = notes
    if reason:
        payload["reason"] = reason
    return payload


def _fetch_supabase_entries(goal: str) -> list[dict[str, Any]]:
    client = _get_supabase_client()
    if client is None:
        return []
    table = os.getenv("SUPABASE_KB_TABLE", "knowledge_base")
    try:
        query = client.table(table).select("*").limit(5)
        if goal:
            try:
                query = query.ilike("goal", f"%{goal[:60]}%")
            except AttributeError:
                pass
        response = query.execute()
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Supabase query failed: %s", exc)
        return []
    data = getattr(response, "data", None)
    if data is None and isinstance(response, dict):
        data = response.get("data")
    return data or []


def _github_request(url: str, *, token: Optional[str]) -> Optional[Any]:
    if requests is None:
        return None
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "system-design-agent",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code >= 400:
            logger.warning("GitHub API error %s for %s", resp.status_code, url)
            return None
        return resp.json()
    except Exception as exc:  # pragma: no cover - network failure
        logger.warning("GitHub API request failed: %s", exc)
        return None


def _tavily_search(query: str) -> list[dict[str, Any]]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key or requests is None:
        return []
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": 5,
        "search_depth": "basic",
    }
    try:
        resp = requests.post(TAVILY_ENDPOINT, json=payload, timeout=15)
        if resp.status_code >= 400:
            logger.warning("Tavily search failed with %s", resp.status_code)
            return []
        data = resp.json()
    except Exception as exc:  # pragma: no cover - network failure
        logger.warning("Tavily search request failed: %s", exc)
        return []
    results = data.get("results") if isinstance(data, dict) else None
    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict)]
    return []


def _summarise_highlights(highlights: list[str]) -> str:
    if not highlights:
        return ""
    bullet_points = "\n".join(f"- {line}" for line in highlights[:5])
    return bullet_points


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
    episodic_messages = load_long_term_messages(
        user_id=user_id,
        process_id=process_id,
        limit=12,
    )
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
    memory_messages: list[BaseMessage] = []
    seen_content: set[str] = set()
    for msg in episodic_messages:
        content = get_content(msg)
        if content and content not in seen_content:
            seen_content.add(content)
            memory_messages.append(msg)
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

    # Ensure metadata is initialized and populated
    existing_metadata = state.get("metadata") or {}
    metadata_updates: Dict[str, Any] = {}
    
    # Preserve existing metadata
    if existing_metadata:
        metadata_updates.update(existing_metadata)
    
    # Log if user_id/thread_id are missing (they should be set by run config)
    # When using LangGraph Studio, users can set metadata in the run config
    # When using the web app, metadata is automatically set via buildRunMetadata
    if not metadata_updates.get("user_id") and not metadata_updates.get("thread_id"):
        logger.debug(
            "orchestrator: metadata missing user_id/thread_id - memory features may be limited. "
            "Set metadata in run config when using Studio, or ensure web app passes metadata."
        )
    elif metadata_updates.get("user_id"):
        logger.debug("orchestrator: user_id found in metadata - memory features enabled")
    
    # Only update metadata if we have changes
    if metadata_updates != existing_metadata:
        updates["metadata"] = metadata_updates

    phase = (state.get("run_phase") or "planner").lower()
    updates.setdefault("run_phase", phase)

    plan_scope = state.get("plan_scope") or {}

    orchestrator_state["last_phase"] = phase
    updates["orchestrator"] = orchestrator_state
    return updates



def planner_agent(state: State) -> Dict[str, any]:
    existing = state.get("planner_state")
    planner_state = _initial_planner_state(existing)
    
    # Get results from subnodes (they update state directly via graph edges)
    plan_scope = state.get("plan_scope") or {}
    plan_state = state.get("plan_state") or {}
    
    # Check status of subnodes
    scope_status = plan_scope.get("status", "").lower()
    steps_status = plan_state.get("status", "").lower()
    scope_completed = scope_status == "completed"
    steps_completed = steps_status == "completed"
    
    # If subnodes are not both complete, routing will handle it
    # This function only aggregates when both are done
    if not (scope_completed and steps_completed):
        # Still update planner_state with what we have
        if scope_completed:
            planner_state["scope"] = plan_scope
        if steps_completed:
            planner_state["steps"] = plan_state
        
        # Return minimal updates - routing will handle next step
        return {
            "planner_state": planner_state,
        }
    
    # Both subnodes are complete - aggregate and check quality/clarifier
    planner_state["scope"] = plan_scope
    planner_state["steps"] = plan_state
    
    # Aggregate status
    statuses = [scope_status, steps_status]
    if any(status == "completed" for status in statuses):
        overall_status = "completed"
    elif any(status == "pending" for status in statuses):
        overall_status = "pending"
    else:
        overall_status = planner_state.get("status") or "pending"
    planner_state["status"] = overall_status
    
    # Aggregate notes
    scope_notes = plan_scope.get("notes") or []
    steps_notes = plan_state.get("notes") or []
    if isinstance(scope_notes, list):
        for note in scope_notes:
            planner_state["notes"] = _append_planner_note(planner_state.get("notes", []), note)
    if isinstance(steps_notes, list):
        for note in steps_notes:
            planner_state["notes"] = _append_planner_note(planner_state.get("notes", []), note)
    
    # Clarifier pauses are disabled for now; proceed without requesting extra input
    
    # Handle quality check
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
            # Reset subnode statuses to allow retry
            return {
                "planner_state": planner_state,
                "plan_scope": {**plan_scope, "status": "pending"},  # Reset to allow retry
                "plan_state": {**plan_state, "status": "pending"},  # Reset to allow retry
                "metadata": updated_meta,
                "run_phase": "planner",
            }
    
    # Finalize and record memory
    summary = _coerce_str(plan_state.get("summary"), max_len=600)
    _record_final_plan_memory(state, summary, plan_state=plan_state)
    
    updates: Dict[str, Any] = {
        "planner_state": planner_state,
        "plan_scope": plan_scope,
        "plan_state": plan_state,
        "run_phase": "research",
    }
    if summary:
        updates["plan"] = summary
    if quality is not None:
        updates["plan_quality"] = quality
    
    return updates


def _record_final_plan_memory(state: State, summary: Optional[str], plan_state: Optional[dict[str, Any]] = None) -> None:
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

    plan_state_data = plan_state or state.get("plan_state") or {}
    steps = plan_state_data.get("steps") or []
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

    # Temporarily disable clarifier interruptions; keep issues for notes/risk
    needs_clarifier = False
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
    notes: list[str] = []
    if blocking_issues:
        notes.append(f"Blocking issues found: {len(blocking_issues)}")
    if info_issues:
        notes.append(f"Info issues found: {len(info_issues)}")
    if not notes:
        notes.append("Scope analysis completed")
    
    return {
        "status": "completed",
        "scope": plan_scope,
        "notes": notes,
        # Keep backward compatibility
        "plan_scope": plan_scope,
    }


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
        quality = _compute_plan_quality(scope, normalized_steps, state)
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
    quality = _compute_plan_quality(scope, normalized_steps, state)
    summary_text = _coerce_str(summary, max_len=600) or "\n".join(
        f"- {step['title']}" for step in normalized_steps
    )

    plan_state_data = {
        "status": "completed",
        "steps": normalized_steps,
        "summary": summary_text,
        "issues": issues,
        "risks": risks,
        "quality": quality,
    }
    
    notes: list[str] = []
    if normalized_steps:
        notes.append(f"Generated {len(normalized_steps)} plan step(s)")
    if quality is not None:
        notes.append(f"Plan quality: {quality:.2f}")
    if not notes:
        notes.append("Plan steps completed")
    
    return {
        "status": "completed",
        "steps": plan_state_data,
        "notes": notes,
        # Keep backward compatibility
        "plan": summary_text,
        "plan_state": plan_state_data,
    }


def knowledge_base_node(state: State) -> Dict[str, Any]:
    metadata = state.get("metadata") or {}
    goal = _coerce_str(state.get("goal"), max_len=320) or ""

    entries = metadata.get("kb_entries")
    sources: list[dict[str, Any]] = []
    note = None
    if isinstance(entries, list) and entries:
        sources = [entry for entry in entries if isinstance(entry, dict)]
        note = "metadata entries"
    else:
        sources = _fetch_supabase_entries(goal)
        note = "supabase lookup" if sources else None

    highlights: list[str] = []
    citations: list[dict[str, Any]] = []
    risks: list[str] = []

    for entry in sources:
        summary = _coerce_str(entry.get("summary") or entry.get("note"), max_len=280)
        if summary:
            highlights.append(summary)
        url = _coerce_str(entry.get("url") or entry.get("link"), max_len=320)
        if url:
            citations.append(
                {
                    "source": "knowledge_base",
                    "url": url,
                    "title": _coerce_str(entry.get("title"), max_len=160) or "Knowledge base reference",
                }
            )
        risk_items = entry.get("risks") or entry.get("warnings") or []
        if isinstance(risk_items, (list, tuple)):
            for risk in risk_items:
                text = _coerce_str(risk, max_len=160)
                if text:
                    risks.append(text)

    status = "completed" if highlights or citations else "skipped"
    reason = None if status == "completed" else "No knowledge base entries returned"
    result = _research_payload(
        "knowledge_base",
        status,
        highlights=_limit_strings(highlights),
        citations=_limit_dicts(citations),
        risks=_limit_strings(risks),
        notes=note,
        reason=reason,
    )
    
    # Store result in research_state.nodes for research_agent to aggregate
    existing_research_state = state.get("research_state") or {}
    existing_nodes = existing_research_state.get("nodes") or {}
    existing_nodes["knowledge_base"] = result
    
    return {
        "research_state": {
            **existing_research_state,
            "nodes": existing_nodes,
        }
    }


def github_api_node(state: State) -> Dict[str, Any]:
    metadata = state.get("metadata") or {}
    repo = metadata.get("github_repo")
    repo_data = metadata.get("github_repo_data")
    issues_data = metadata.get("github_issue_data")
    note: Optional[str] = None

    if isinstance(repo_data, dict):
        note = "metadata snapshot"
    else:
        repo = _coerce_str(repo, max_len=120)
        if not repo:
            result = _research_payload(
                "github_api",
                "skipped",
                notes="github_repo metadata missing",
                reason="github_repo not set in metadata",
            )
            existing_research_state = state.get("research_state") or {}
            existing_nodes = existing_research_state.get("nodes") or {}
            existing_nodes["github_api"] = result
            return {
                "research_state": {
                    **existing_research_state,
                    "nodes": existing_nodes,
                }
            }
        if requests is None:
            result = _research_payload(
                "github_api",
                "skipped",
                notes="requests library unavailable",
                reason="requests dependency missing",
            )
            existing_research_state = state.get("research_state") or {}
            existing_nodes = existing_research_state.get("nodes") or {}
            existing_nodes["github_api"] = result
            return {
                "research_state": {
                    **existing_research_state,
                    "nodes": existing_nodes,
                }
            }
        token = _coerce_str(metadata.get("github_token"), max_len=200) or _coerce_str(
            os.getenv("GITHUB_TOKEN"), max_len=200
        )
        base_url = f"https://api.github.com/repos/{repo}"
        repo_data = _github_request(base_url, token=token) or {}
        issues_resp = _github_request(
            f"{base_url}/issues?state=open&per_page=5", token=token
        )
        issues_data = (
            issues_resp
            if isinstance(issues_resp, list)
            else issues_resp.get("items", [])
            if isinstance(issues_resp, dict)
            else []
        )
        note = "github api"

    highlights: list[str] = []
    citations: list[dict[str, Any]] = []
    risks: list[str] = []

    description = _coerce_str(repo_data.get("description"), max_len=240)
    if description:
        highlights.append(f"{repo or repo_data.get('full_name')}: {description}")
    language = _coerce_str(repo_data.get("language"), max_len=80)
    if language:
        highlights.append(f"Primary language: {language}")
    stars = repo_data.get("stargazers_count")
    if isinstance(stars, int):
        highlights.append(f"GitHub stars: {stars}")
    html_url = _coerce_str(repo_data.get("html_url"), max_len=320)
    if html_url:
        citations.append({"source": "github_repo", "url": html_url, "title": repo_data.get("full_name") or repo})

    for issue in issues_data[:5]:
        if not isinstance(issue, dict):
            continue
        title = _coerce_str(issue.get("title"), max_len=200)
        if title:
            risks.append(f"Issue: {title}")
        link = _coerce_str(issue.get("html_url"), max_len=320)
        if link:
            citations.append({"source": "github_issue", "url": link, "title": title or "Issue"})

    status = "completed" if highlights or citations else "skipped"
    reason = None if status == "completed" else "GitHub data unavailable"
    result = _research_payload(
        "github_api",
        status,
        highlights=_limit_strings(highlights),
        citations=_limit_dicts(citations),
        risks=_limit_strings(risks),
        notes=note,
        reason=reason,
    )
    
    # Store result in research_state.nodes for research_agent to aggregate
    existing_research_state = state.get("research_state") or {}
    existing_nodes = existing_research_state.get("nodes") or {}
    existing_nodes["github_api"] = result
    
    return {
        "research_state": {
            **existing_research_state,
            "nodes": existing_nodes,
        }
    }


def web_search_node(state: State) -> Dict[str, Any]:
    metadata = state.get("metadata") or {}
    manual_results = metadata.get("web_results")
    query = _coerce_str(metadata.get("search_query"), max_len=320) or _coerce_str(state.get("goal"), max_len=320)

    if isinstance(manual_results, list) and manual_results:
        results = [item for item in manual_results if isinstance(item, dict)]
        note = "metadata results"
    else:
        if not query:
            result = _research_payload(
                "web_search",
                "skipped",
                notes="No query available",
                reason="goal and search_query missing",
            )
            existing_research_state = state.get("research_state") or {}
            existing_nodes = existing_research_state.get("nodes") or {}
            existing_nodes["web_search"] = result
            return {
                "research_state": {
                    **existing_research_state,
                    "nodes": existing_nodes,
                }
            }
        results = _tavily_search(query)
        note = "tavily" if results else None

    highlights: list[str] = []
    citations: list[dict[str, Any]] = []

    for item in results:
        snippet = _coerce_str(item.get("content") or item.get("snippet"), max_len=320)
        title = _coerce_str(item.get("title"), max_len=160)
        url = _coerce_str(item.get("url"), max_len=320)
        if snippet:
            highlights.append(snippet)
        if url:
            citations.append({"source": "web_search", "url": url, "title": title or snippet or "search result"})

    status = "completed" if highlights or citations else "skipped"
    reason = None if status == "completed" else "No web results returned"
    result = _research_payload(
        "web_search",
        status,
        highlights=_limit_strings(highlights),
        citations=_limit_dicts(citations),
        risks=[],
        notes=note,
        reason=reason,
    )
    
    # Store result in research_state.nodes for research_agent to aggregate
    existing_research_state = state.get("research_state") or {}
    existing_nodes = existing_research_state.get("nodes") or {}
    existing_nodes["web_search"] = result
    
    return {
        "research_state": {
            **existing_research_state,
            "nodes": existing_nodes,
        }
    }


def research_agent(state: State) -> Dict[str, any]:
    existing = state.get("research_state")
    research_state = _initial_research_state(existing)
    
    # Get results from subnodes (they update state directly via graph edges)
    nodes = research_state.get("nodes") or {}
    
    # Check status of subnodes
    kb_result = nodes.get("knowledge_base", {})
    github_result = nodes.get("github_api", {})
    web_result = nodes.get("web_search", {})
    
    kb_status = kb_result.get("status", "").lower() if isinstance(kb_result, dict) else ""
    github_status = github_result.get("status", "").lower() if isinstance(github_result, dict) else ""
    web_status = web_result.get("status", "").lower() if isinstance(web_result, dict) else ""
    
    kb_completed = kb_status == "completed" or kb_status == "skipped"
    github_completed = github_status == "completed" or github_status == "skipped"
    web_completed = web_status == "completed" or web_status == "skipped"
    
    # If subnodes are not all complete, routing will handle it
    # This function only aggregates when all are done
    if not (kb_completed and github_completed and web_completed):
        # Still update research_state with what we have
        if kb_completed:
            research_state["nodes"]["knowledge_base"] = kb_result
        if github_completed:
            research_state["nodes"]["github_api"] = github_result
        if web_completed:
            research_state["nodes"]["web_search"] = web_result
        
        # Return minimal updates - routing will handle next step
        return {
            "research_state": research_state,
        }
    
    # All subnodes are complete - aggregate results
    node_outputs = {
        "knowledge_base_node": kb_result,
        "github_api_node": github_result,
        "web_search_node": web_result,
    }
    
    # Store all node outputs
    research_state["nodes"] = {
        "knowledge_base": kb_result,
        "github_api": github_result,
        "web_search": web_result,
    }
    
    # Aggregate notes
    for result in node_outputs.values():
        if isinstance(result, dict):
            note_hint = result.get("notes") or result.get("reason") or result.get("status")
            research_state["notes"] = _append_research_note(research_state.get("notes", []), note_hint)
    
    # Aggregate highlights, citations, risks from all subnodes
    highlights = _limit_strings(
        [
            _coerce_str(item, max_len=320) or ""
            for result in node_outputs.values()
            if isinstance(result, dict)
            for item in result.get("highlights", [])
        ],
        limit=12,
    )
    citations = _limit_dicts(
        [
            cite
            for result in node_outputs.values()
            if isinstance(result, dict)
            for cite in result.get("citations", [])
            if isinstance(cite, dict)
        ],
        limit=12,
    )
    risks = _limit_strings(
        [
            _coerce_str(item, max_len=200) or ""
            for result in node_outputs.values()
            if isinstance(result, dict)
            for item in result.get("risks", [])
        ],
        limit=8,
    )
    
    # Update research_state with aggregated data
    research_state["highlights"] = highlights
    research_state["citations"] = citations
    research_state["risks"] = risks
    
    # Determine overall status
    statuses = [
        _coerce_str(result.get("status"), max_len=16) or ""
        for result in node_outputs.values()
        if isinstance(result, dict)
    ]
    lowered = [status.lower() for status in statuses if status]
    if any(status == "completed" for status in lowered):
        overall_status = "completed"
    elif any(status == "pending" for status in lowered):
        overall_status = "pending"
    elif lowered:
        overall_status = "skipped"
    else:
        overall_status = research_state.get("status") or "pending"
    research_state["status"] = overall_status
    
    summary = _summarise_highlights(highlights)
    research_state["summary"] = summary
    
    return {
        "research_state": research_state,
        "research_highlights": highlights,
        "research_citations": citations,
        "research_summary": summary,
        "run_phase": "design",
    }


def _initial_research_state(existing: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = existing if isinstance(existing, dict) else {}
    return {
        "status": _coerce_str(data.get("status")) or "pending",
        "nodes": data.get("nodes") or {},
        "highlights": _coerce_str_list(data.get("highlights"), max_items=12, max_len=320),
        "citations": _limit_dicts(data.get("citations") or [], limit=12),
        "risks": _coerce_str_list(data.get("risks"), max_items=8, max_len=200),
        "notes": _coerce_str_list(data.get("notes"), max_items=8, max_len=160),
    }


def _initial_planner_state(existing: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = existing if isinstance(existing, dict) else {}
    return {
        "status": _coerce_str(data.get("status")) or "pending",
        "scope": data.get("scope") or {},
        "steps": data.get("steps") or {},
        "notes": _coerce_str_list(data.get("notes"), max_items=8, max_len=160),
    }


def _initial_eval_state(existing: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = existing if isinstance(existing, dict) else {}
    return {
        "status": _coerce_str(data.get("status")) or "pending",
        "telemetry": data.get("telemetry") or {},
        "scores": data.get("scores") or {},
        "final_judgement": data.get("final_judgement") or {},
        "needs_attention": bool(data.get("needs_attention")) if data.get("needs_attention") is not None else False,
        "notes": _coerce_str_list(data.get("notes"), max_items=8, max_len=200),
    }


def _initial_design_state(existing: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = existing if isinstance(existing, dict) else {}
    return {
        "status": _coerce_str(data.get("status")) or "pending",
        "components": data.get("components") or {},
        "diagram": data.get("diagram") or {},
        "costs": data.get("costs") or {},
        "notes": _coerce_str_list(data.get("notes"), max_items=8, max_len=160),
    }


def _plan_has_component_hints(plan_state: dict[str, Any]) -> bool:
    steps = plan_state.get("steps") or []
    if not isinstance(steps, list):
        return False
    keywords = {"component", "service", "module", "microservice", "database"}
    for step in steps:
        if not isinstance(step, dict):
            continue
        text_parts = [
            _coerce_str(step.get("title"), max_len=200) or "",
            _coerce_str(step.get("detail"), max_len=400) or "",
        ]
        text = " ".join(text_parts).lower()
        if any(keyword in text for keyword in keywords):
            return True
    return False


def _design_subnode_order(plan_state: dict[str, Any]) -> list[str]:
    cost_node = "cost_est_node"
    component_first = _plan_has_component_hints(plan_state)
    primary = ["component_library_node", "diagram_generator_node"]
    if not component_first:
        primary.reverse()
    return primary + [cost_node]


def _call_research_subnode(node_name: str, state: State) -> dict[str, Any]:
    func = globals().get(node_name)
    if not callable(func):
        note = f"{node_name} not implemented"
        return {"status": "skipped", "notes": note}
    try:
        result = func(state)
        if not isinstance(result, dict):
            raise ValueError(f"{node_name} must return a dict result.")
        return result
    except Exception as exc:  # pragma: no cover - defensive guardrail
        logger.warning("Research subnode %s failed: %s", node_name, exc)
        return {"status": "skipped", "notes": f"{node_name} error: {exc}"}


def _call_eval_subnode(node_name: str, state: State) -> dict[str, Any]:
    func = globals().get(node_name)
    if not callable(func):
        note = f"{node_name} not implemented"
        return {"status": "skipped", "notes": [note]}
    try:
        result = func(state)
        if not isinstance(result, dict):
            raise ValueError(f"{node_name} must return a dict result.")
        return result
    except Exception as exc:  # pragma: no cover - defensive guardrail
        logger.warning("Eval subnode %s failed: %s", node_name, exc)
        return {"status": "skipped", "notes": [f"{node_name} error: {exc}"]}


def _call_planner_subnode(node_name: str, state: State) -> dict[str, Any]:
    func = globals().get(node_name)
    if not callable(func):
        note = f"{node_name} not implemented"
        return {"status": "skipped", "notes": note}
    try:
        result = func(state)
        if not isinstance(result, dict):
            raise ValueError(f"{node_name} must return a dict result.")
        return result
    except Exception as exc:  # pragma: no cover - defensive guardrail
        logger.warning("Planner subnode %s failed: %s", node_name, exc)
        return {"status": "skipped", "notes": f"{node_name} error: {exc}"}


def _call_design_subnode(node_name: str, state: State) -> dict[str, Any]:
    func = globals().get(node_name)
    if not callable(func):
        note = f"{node_name} not implemented"
        return {"status": "skipped", "notes": note}
    try:
        result = func(state)
        if not isinstance(result, dict):
            raise ValueError(f"{node_name} must return a dict result.")
        return result
    except Exception as exc:  # pragma: no cover - defensive guardrail
        logger.warning("Design subnode %s failed: %s", node_name, exc)
        return {"status": "skipped", "notes": f"{node_name} error: {exc}"}


def _append_research_note(notes: list[str], message: Optional[str]) -> list[str]:
    text = _coerce_str(message, max_len=160)
    if text and text not in notes:
        updated = notes + [text]
        return updated[-8:]
    return notes


def _append_planner_note(notes: list[str], message: Optional[str]) -> list[str]:
    text = _coerce_str(message, max_len=160)
    if text and text not in notes:
        updated = notes + [text]
        return updated[-8:]
    return notes


def _append_eval_note(notes: list[str], message: Optional[str]) -> list[str]:
    text = _coerce_str(message, max_len=200)
    if text and text not in notes:
        updated = notes + [text]
        return updated[-8:]
    return notes


def _append_design_note(notes: list[str], message: Optional[str]) -> list[str]:
    text = _coerce_str(message, max_len=160)
    if text and text not in notes:
        updated = notes + [text]
        return updated[-8:]
    return notes


def component_library_node(state: State) -> Dict[str, Any]:
    component_file = os.path.join(
        os.path.dirname(__file__),
        "component_library.json"
    )
    components: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {
        "source_path": component_file,
        "count": 0,
    }
    notes: list[str] = []
    
    try:
        if not os.path.exists(component_file):
            notes.append(f"Component library file not found: {component_file}")
            result = {
                "status": "skipped",
                "components": [],
                "metadata": metadata,
                "notes": notes,
            }
            existing_design_state = state.get("design_state") or {}
            existing_design_state["components"] = result
            return {
                "design_state": existing_design_state,
            }
        
        with open(component_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        
        if not isinstance(raw_data, list):
            notes.append("Component library file does not contain a JSON array")
            result = {
                "status": "skipped",
                "components": [],
                "metadata": metadata,
                "notes": notes,
            }
            existing_design_state = state.get("design_state") or {}
            existing_design_state["components"] = result
            return {
                "design_state": existing_design_state,
            }
        
        # Normalize and validate entries
        for idx, entry in enumerate(raw_data):
            if not isinstance(entry, dict):
                continue
            component_id = _coerce_str(entry.get("id"), max_len=64)
            if not component_id:
                continue
            
            # Keep essential fields, coerce others
            normalized: dict[str, Any] = {
                "id": component_id,
                "name": _coerce_str(entry.get("name"), max_len=120) or component_id,
                "type": _coerce_str(entry.get("type"), max_len=32) or "unknown",
                "description": _coerce_str(entry.get("description"), max_len=400) or "",
            }
            
            # Optional fields
            if entry.get("owner"):
                normalized["owner"] = _coerce_str(entry.get("owner"), max_len=80)
            if entry.get("inputs"):
                normalized["inputs"] = _coerce_str_list(entry.get("inputs"), max_items=8, max_len=200)
            if entry.get("outputs"):
                normalized["outputs"] = _coerce_str_list(entry.get("outputs"), max_items=8, max_len=200)
            if entry.get("dependencies"):
                normalized["dependencies"] = _coerce_str_list(entry.get("dependencies"), max_items=8, max_len=120)
            if entry.get("protocols"):
                normalized["protocols"] = _coerce_str_list(entry.get("protocols"), max_items=6, max_len=80)
            if entry.get("refs"):
                normalized["refs"] = _coerce_str_list(entry.get("refs"), max_items=5, max_len=320)
            if entry.get("repos"):
                normalized["repos"] = _coerce_str_list(entry.get("repos"), max_items=5, max_len=200)
            
            components.append(normalized)
        
        metadata["count"] = len(components)
        
        if components:
            status = "completed"
            notes.append(f"Loaded {len(components)} component(s) from library")
        else:
            status = "skipped"
            notes.append("Component library file is empty or contains no valid entries")
        
    except json.JSONDecodeError as exc:
        logger.warning("component_library_node: JSON parse error: %s", exc)
        notes.append(f"Failed to parse component library JSON: {exc}")
        result = {
            "status": "skipped",
            "components": [],
            "metadata": metadata,
            "notes": notes,
        }
        existing_design_state = state.get("design_state") or {}
        existing_design_state["components"] = result
        return {
            "design_state": existing_design_state,
        }
    except Exception as exc:  # pragma: no cover - defensive guardrail
        logger.warning("component_library_node: unexpected error: %s", exc)
        notes.append(f"Error loading component library: {exc}")
        result = {
            "status": "skipped",
            "components": [],
            "metadata": metadata,
            "notes": notes,
        }
        existing_design_state = state.get("design_state") or {}
        existing_design_state["components"] = result
        return {
            "design_state": existing_design_state,
        }
    
    result = {
        "status": status,
        "components": components,
        "metadata": metadata,
        "notes": notes,
    }
    
    # Store result in design_state.components for design_agent to aggregate
    existing_design_state = state.get("design_state") or {}
    existing_design_state["components"] = result
    
    return {
        "design_state": existing_design_state,
    }


def diagram_generator_node(state: State) -> Dict[str, Any]:
    design_state = state.get("design_state") or {}
    plan_state = state.get("plan_state") or {}
    components_data = design_state.get("components") or {}
    components_list = components_data.get("components") or []
    
    notes: list[str] = []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    
    # Extract nodes from components
    for comp in components_list:
        if not isinstance(comp, dict):
            continue
        comp_id = _coerce_str(comp.get("id"), max_len=64)
        comp_name = _coerce_str(comp.get("name"), max_len=120) or comp_id
        comp_type = _coerce_str(comp.get("type"), max_len=32) or "unknown"
        
        if not comp_id or comp_id in node_ids:
            continue
        
        node_ids.add(comp_id)
        nodes.append({
            "id": comp_id,
            "label": comp_name,
            "type": comp_type,
        })
        
        # Extract dependency edges
        deps = comp.get("dependencies") or []
        if isinstance(deps, list):
            for dep in deps:
                dep_str = _coerce_str(dep, max_len=120)
                if not dep_str:
                    continue
                # Try to match dependency to a component ID (simple heuristic)
                dep_id = None
                for other_comp in components_list:
                    if not isinstance(other_comp, dict):
                        continue
                    other_id = _coerce_str(other_comp.get("id"), max_len=64)
                    other_name = _coerce_str(other_comp.get("name"), max_len=120) or ""
                    if other_id and (other_id.lower() in dep_str.lower() or other_name.lower() in dep_str.lower()):
                        dep_id = other_id
                        break
                
                if dep_id and dep_id in node_ids:
                    edges.append({
                        "source": dep_id,
                        "target": comp_id,
                        "label": dep_str[:80],
                        "type": "dependency",
                    })
    plan_steps = plan_state.get("steps") or []
    if isinstance(plan_steps, list):
        for step in plan_steps:
            if not isinstance(step, dict):
                continue
            step_title = _coerce_str(step.get("title"), max_len=200) or ""
            step_detail = _coerce_str(step.get("detail"), max_len=400) or ""
            step_text = f"{step_title} {step_detail}".lower()

            mentioned_ids: list[str] = []
            for comp in components_list:
                if not isinstance(comp, dict):
                    continue
                comp_id = _coerce_str(comp.get("id"), max_len=64)
                comp_name = _coerce_str(comp.get("name"), max_len=120) or ""
                if comp_id and comp_id in node_ids:
                    if comp_id.lower() in step_text or comp_name.lower() in step_text:
                        mentioned_ids.append(comp_id)

            for i in range(len(mentioned_ids) - 1):
                edges.append({
                    "source": mentioned_ids[i],
                    "target": mentioned_ids[i + 1],
                    "label": step_title[:60] if step_title else "data_flow",
                    "type": "data_flow",
                })
    
    # Generate Mermaid text
    mermaid_lines: list[str] = ["flowchart TD"]
    
    # Add nodes with type-based shapes
    for node in nodes:
        node_id = node["id"]
        node_label = node["label"].replace('"', "'")
        node_type = node.get("type", "").lower()
        
        if node_type == "db":
            mermaid_lines.append(f'    {node_id}[( "{node_label}" )]')
        elif node_type == "api":
            mermaid_lines.append(f'    {node_id}["{node_label}"]')
        else:
            mermaid_lines.append(f'    {node_id}["{node_label}"]')
    
    # Add edges
    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        label = edge.get("label", "")
        edge_type = edge.get("type", "")
        
        label_part = f'|"{label}"|' if label else ""
        mermaid_lines.append(f'    {source} -->{label_part} {target}')
    
    mermaid_text = "\n".join(mermaid_lines) if mermaid_lines else ""
    
    # Build simple JSON graph
    graph_json = {
        "nodes": nodes,
        "edges": edges,
    }
    
    # Determine status
    if nodes:
        status = "completed"
        notes.append(f"Generated diagram with {len(nodes)} node(s) and {len(edges)} edge(s)")
    else:
        status = "skipped"
        notes.append("No components found in design_state to generate diagram")
    
    result = {
        "status": status,
        "mermaid": mermaid_text,
        "graph": graph_json,
        "notes": notes,
    }
    
    # Store result in design_state.diagram for design_agent to aggregate
    existing_design_state = state.get("design_state") or {}
    existing_design_state["diagram"] = result
    
    return {
        "design_state": existing_design_state,
    }


def cost_est_node(state: State) -> Dict[str, Any]:
    design_state = state.get("design_state") or {}
    plan_state = state.get("plan_state") or {}
    components_data = design_state.get("components") or {}
    components_list = components_data.get("components") or []
    plan_summary = _coerce_str(plan_state.get("summary"), max_len=600) or ""
    
    if not components_list:
        result = {
            "status": "skipped",
            "estimates": [],
            "total": {"monthly_usd": 0, "one_time_usd": 0},
        }
        existing_design_state = state.get("design_state") or {}
        existing_design_state["costs"] = result
        return {
            "design_state": existing_design_state,
        }
    comp_summaries: list[str] = []
    for comp in components_list:
        if not isinstance(comp, dict):
            continue
        comp_id = _coerce_str(comp.get("id"), max_len=64) or "unknown"
        comp_name = _coerce_str(comp.get("name"), max_len=120) or comp_id
        comp_type = _coerce_str(comp.get("type"), max_len=32) or "unknown"
        comp_desc = _coerce_str(comp.get("description"), max_len=200) or ""
        comp_summaries.append(f"- {comp_id} ({comp_name}, type: {comp_type}): {comp_desc}")
    
    components_text = "\n".join(comp_summaries) if comp_summaries else "No components listed"
    
    schema_desc = json.dumps(
        {
            "estimates": [
                {
                    "component_id": "auth-service-supabase",
                    "name": "Component name",
                    "monthly_usd": 50.0,
                    "one_time_usd": 0.0,
                    "notes": "Brief cost rationale",
                }
            ],
        },
        ensure_ascii=False,
    )
    
    sys = SystemMessage(content=(
        "You are a cost estimation expert for system architectures. "
        "Return JSON only matching this schema:\n"
        f"{schema_desc}\n"
        "Provide approximate cost estimates in USD. "
        "monthly_usd: recurring monthly costs (hosting, services, maintenance). "
        "one_time_usd: one-time setup/initial costs (development, migration, setup). "
        "Include a brief notes field explaining the estimate rationale. "
        "Estimates should be approximate and reasonable for the component type and scale."
    ))
    
    prompt_lines = ["Estimate costs for the following architecture components:\n"]
    prompt_lines.append(components_text)
    if plan_summary:
        prompt_lines.append(f"\nPlan context:\n{plan_summary}")
    prompt = "\n".join(prompt_lines)
    
    run_id = state.get("metadata", {}).get("run_id")
    try:
        raw = call_brain(
            [sys, HumanMessage(content=prompt)],
            state=state,
            run_id=run_id,
            node="cost_est_node",
        )
        parsed = json_only(raw) or {}
        estimates_raw = parsed.get("estimates") or []
    except Exception as exc:
        logger.warning("cost_est_node: LLM call failed: %s", exc)
        return {
            "status": "skipped",
            "estimates": [],
            "total": {"monthly_usd": 0, "one_time_usd": 0},
        }
    estimates: list[dict[str, Any]] = []
    total_monthly = 0.0
    total_one_time = 0.0
    
    for est in estimates_raw:
        if not isinstance(est, dict):
            continue
        comp_id = _coerce_str(est.get("component_id"), max_len=64)
        name = _coerce_str(est.get("name"), max_len=120) or comp_id or "unknown"
        monthly = est.get("monthly_usd")
        one_time = est.get("one_time_usd")
        notes = _coerce_str(est.get("notes"), max_len=200) or ""
        try:
            monthly_val = float(monthly) if monthly is not None else 0.0
            one_time_val = float(one_time) if one_time is not None else 0.0
        except (TypeError, ValueError):
            monthly_val = 0.0
            one_time_val = 0.0
        if comp_id:
            estimates.append({
                "component_id": comp_id,
                "name": name,
                "monthly_usd": monthly_val,
                "one_time_usd": one_time_val,
                "notes": notes,
            })
            total_monthly += monthly_val
            total_one_time += one_time_val
    
    status = "completed" if estimates else "skipped"
    
    result = {
        "status": status,
        "estimates": estimates,
        "total": {
            "monthly_usd": total_monthly,
            "one_time_usd": total_one_time,
        },
    }
    
    # Store result in design_state.costs for design_agent to aggregate
    existing_design_state = state.get("design_state") or {}
    existing_design_state["costs"] = result
    
    return {
        "design_state": existing_design_state,
    }


def design_agent(state: State) -> Dict[str, any]:
    plan_state = state.get("plan_state") or {}
    existing = state.get("design_state")
    design_state = _initial_design_state(existing)

    # Get results from subnodes (they update state directly via graph edges)
    components_result = design_state.get("components", {})
    diagram_result = design_state.get("diagram", {})
    costs_result = design_state.get("costs", {})
    
    # Check status of subnodes
    components_status = components_result.get("status", "").lower() if isinstance(components_result, dict) else ""
    diagram_status = diagram_result.get("status", "").lower() if isinstance(diagram_result, dict) else ""
    costs_status = costs_result.get("status", "").lower() if isinstance(costs_result, dict) else ""
    
    components_completed = components_status == "completed" or components_status == "skipped"
    diagram_completed = diagram_status == "completed" or diagram_status == "skipped"
    costs_completed = costs_status == "completed" or costs_status == "skipped"
    
    # If subnodes are not all complete, routing will handle it
    # This function only aggregates when all are done
    if not (components_completed and diagram_completed and costs_completed):
        # Still update design_state with what we have
        if components_completed:
            design_state["components"] = components_result
        if diagram_completed:
            design_state["diagram"] = diagram_result
        if costs_completed:
            design_state["costs"] = costs_result
        
        # Return minimal updates - routing will handle next step
        return {
            "design_state": design_state,
        }
    
    # All subnodes are complete - aggregate results
    design_state["components"] = components_result
    design_state["diagram"] = diagram_result
    design_state["costs"] = costs_result
    
    # Aggregate notes
    for result in [components_result, diagram_result, costs_result]:
        if isinstance(result, dict):
            notes = result.get("notes")
            if isinstance(notes, list):
                for note in notes:
                    design_state["notes"] = _append_design_note(design_state.get("notes", []), note)
            elif notes:
                design_state["notes"] = _append_design_note(design_state.get("notes", []), notes)
    
    # Determine overall status
    statuses = [components_status, diagram_status, costs_status]
    lowered = [status.lower() for status in statuses if status]
    if any(status == "completed" for status in lowered):
        overall_status = "completed"
    elif any(status == "pending" for status in lowered):
        overall_status = "pending"
    elif lowered:
        overall_status = "skipped"
    else:
        overall_status = design_state.get("status") or "pending"
    design_state["status"] = overall_status

    return {
        "design_state": design_state,
        "run_phase": "critic",
    }

def _initial_critic_state(existing: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = existing if isinstance(existing, dict) else {}
    return {
        "status": _coerce_str(data.get("status")) or "pending",
        "review": data.get("review") or {},
        "hallucination": data.get("hallucination") or {},
        "risk": data.get("risk") or {},
        "notes": _coerce_str_list(data.get("notes"), max_items=8, max_len=200),
    }


def _call_critic_subnode(node_name: str, state: State) -> dict[str, Any]:
    func = globals().get(node_name)
    if not callable(func):
        return {"status": "skipped", "notes": [f"{node_name} not implemented"]}
    try:
        result = func(state)
        if not isinstance(result, dict):
            raise ValueError(f"{node_name} must return a dict result.")
        return result
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Critic subnode %s failed: %s", node_name, exc)
        return {"status": "skipped", "notes": [f"{node_name} error: {exc}"]}


def _append_critic_note(notes: list[str], message: Optional[str]) -> list[str]:
    text = _coerce_str(message, max_len=200)
    if text and text not in notes:
        updated = notes + [text]
        return updated[-8:]
    return notes


def review_node(state: State) -> Dict[str, Any]:
    design_state = state.get("design_state") or {}
    plan_state = state.get("plan_state") or {}
    research_state = state.get("research_state") or {}

    components = design_state.get("components", {}).get("components") or []
    comp_titles = [ _coerce_str(c.get("name"), max_len=80) or c.get("id") for c in components if isinstance(c, dict) ]
    comp_summary = "\n".join(f"- {c}" for c in comp_titles if c)
    plan_summary = _coerce_str(plan_state.get("summary"), max_len=600) or ""
    research_summary = _coerce_str(research_state.get("summary"), max_len=600) or ""

    schema_desc = json.dumps(
        {
            "status": "completed",
            "notes": ["short finding or issue"],
        },
        ensure_ascii=False,
    )
    sys = SystemMessage(content=(
        "You are a senior reviewer. Evaluate the proposed architecture for clarity, completeness, and feasibility.\n"
        f"Return JSON only with this shape:\n{schema_desc}\n"
        "Keep notes concise. Point out gaps, unclear parts, or missing dependencies."
    ))

    prompt_lines = []
    if plan_summary:
        prompt_lines.append(f"Plan summary:\n{plan_summary}")
    if research_summary:
        prompt_lines.append(f"\nResearch summary:\n{research_summary}")
    if comp_summary:
        prompt_lines.append(f"\nComponents:\n{comp_summary}")
    prompt = "\n".join(prompt_lines) if prompt_lines else "No plan/components provided."

    run_id = state.get("metadata", {}).get("run_id")
    raw = call_brain([sys, HumanMessage(content=prompt)], state=state, run_id=run_id, node="review_node")
    parsed = json_only(raw) or {}
    notes = _coerce_str_list(parsed.get("notes"), max_items=8, max_len=200)
    status = _coerce_str(parsed.get("status"), max_len=16) or ("completed" if notes else "skipped")

    result = {
        "status": status,
        "notes": notes,
    }
    
    # Store result in critic_state.review for critic_agent to aggregate
    existing_critic_state = state.get("critic_state") or {}
    existing_critic_state["review"] = result
    
    return {
        "critic_state": existing_critic_state,
    }


def hallucination_check_node(state: State) -> Dict[str, Any]:
    design_state = state.get("design_state") or {}
    plan_state = state.get("plan_state") or {}
    research_state = state.get("research_state") or {}

    plan_summary = _coerce_str(plan_state.get("summary"), max_len=600) or ""
    research_summary = _coerce_str(research_state.get("summary"), max_len=600) or ""
    design_notes = _coerce_str_list(design_state.get("notes"), max_items=8, max_len=200)

    schema_desc = json.dumps(
        {
            "status": "completed",
            "notes": ["hallucination or inconsistency observed"],
        },
        ensure_ascii=False,
    )
    sys = SystemMessage(content=(
        "You are checking for hallucinations/inconsistencies. Compare the design against plan and research context.\n"
        f"Return JSON only with this shape:\n{schema_desc}\n"
        "Flag contradictions, ungrounded claims, or missing support. Keep notes brief."
    ))

    prompt_lines = []
    if plan_summary:
        prompt_lines.append(f"Plan summary:\n{plan_summary}")
    if research_summary:
        prompt_lines.append(f"\nResearch summary:\n{research_summary}")
    if design_notes:
        prompt_lines.append("\nDesign notes:\n" + "\n".join(f"- {n}" for n in design_notes))
    prompt = "\n".join(prompt_lines) if prompt_lines else "No context provided."

    run_id = state.get("metadata", {}).get("run_id")
    raw = call_brain([sys, HumanMessage(content=prompt)], state=state, run_id=run_id, node="hallucination_check_node")
    parsed = json_only(raw) or {}
    notes = _coerce_str_list(parsed.get("notes"), max_items=8, max_len=200)
    status = _coerce_str(parsed.get("status"), max_len=16) or ("completed" if notes else "skipped")

    result = {
        "status": status,
        "notes": notes,
    }
    
    # Store result in critic_state.hallucination for critic_agent to aggregate
    existing_critic_state = state.get("critic_state") or {}
    existing_critic_state["hallucination"] = result
    
    return {
        "critic_state": existing_critic_state,
    }


def risk_node(state: State) -> Dict[str, Any]:
    design_state = state.get("design_state") or {}
    plan_state = state.get("plan_state") or {}

    plan_summary = _coerce_str(plan_state.get("summary"), max_len=600) or ""
    components = design_state.get("components", {}).get("components") or []
    comp_titles = [ _coerce_str(c.get("name"), max_len=80) or c.get("id") for c in components if isinstance(c, dict) ]
    comp_summary = "\n".join(f"- {c}" for c in comp_titles if c)

    schema_desc = json.dumps(
        {
            "status": "completed",
            "notes": ["risk description"],
        },
        ensure_ascii=False,
    )
    sys = SystemMessage(content=(
        "You assess architecture risks (scaling, reliability, data, security). Return JSON only:\n"
        f"{schema_desc}\n"
        "List concise risks; note major blockers explicitly."
    ))

    prompt_lines = []
    if plan_summary:
        prompt_lines.append(f"Plan summary:\n{plan_summary}")
    if comp_summary:
        prompt_lines.append(f"\nComponents:\n{comp_summary}")
    prompt = "\n".join(prompt_lines) if prompt_lines else "No plan/components provided."

    run_id = state.get("metadata", {}).get("run_id")
    raw = call_brain([sys, HumanMessage(content=prompt)], state=state, run_id=run_id, node="risk_node")
    parsed = json_only(raw) or {}
    notes = _coerce_str_list(parsed.get("notes"), max_items=8, max_len=200)
    status = _coerce_str(parsed.get("status"), max_len=16) or ("completed" if notes else "skipped")

    result = {
        "status": status,
        "notes": notes,
    }
    
    # Store result in critic_state.risk for critic_agent to aggregate
    existing_critic_state = state.get("critic_state") or {}
    existing_critic_state["risk"] = result
    
    return {
        "critic_state": existing_critic_state,
    }


def critic_agent(state: State) -> Dict[str, any]:
    existing = state.get("critic_state")
    critic_state = _initial_critic_state(existing)

    # Get results from subnodes (they update state directly via graph edges)
    review_result = critic_state.get("review", {})
    hallucination_result = critic_state.get("hallucination", {})
    risk_result = critic_state.get("risk", {})
    
    # Check status of subnodes
    review_status = review_result.get("status", "").lower() if isinstance(review_result, dict) else ""
    hallucination_status = hallucination_result.get("status", "").lower() if isinstance(hallucination_result, dict) else ""
    risk_status = risk_result.get("status", "").lower() if isinstance(risk_result, dict) else ""
    
    review_completed = review_status == "completed" or review_status == "skipped"
    hallucination_completed = hallucination_status == "completed" or hallucination_status == "skipped"
    risk_completed = risk_status == "completed" or risk_status == "skipped"
    
    # If subnodes are not all complete, routing will handle it
    # This function only aggregates when all are done
    if not (review_completed and hallucination_completed and risk_completed):
        # Still update critic_state with what we have
        if review_completed:
            critic_state["review"] = review_result
        if hallucination_completed:
            critic_state["hallucination"] = hallucination_result
        if risk_completed:
            critic_state["risk"] = risk_result
        
        # Return minimal updates - routing will handle next step
        return {
            "critic_state": critic_state,
        }
    
    # All subnodes are complete - aggregate results
    critic_state["review"] = review_result
    critic_state["hallucination"] = hallucination_result
    critic_state["risk"] = risk_result
    
    # Aggregate notes
    for result in [review_result, hallucination_result, risk_result]:
        if isinstance(result, dict):
            notes = result.get("notes")
            if isinstance(notes, list):
                for note in notes:
                    critic_state["notes"] = _append_critic_note(critic_state.get("notes", []), note)
            elif notes:
                critic_state["notes"] = _append_critic_note(critic_state.get("notes", []), notes)

    # Determine overall status
    statuses = [review_status, hallucination_status, risk_status]
    lowered = [s.lower() for s in statuses if s]
    if any(s == "completed" for s in lowered):
        overall = "completed"
    elif any(s == "pending" for s in lowered):
        overall = "pending"
    elif lowered:
        overall = "skipped"
    else:
        overall = critic_state.get("status") or "pending"
    critic_state["status"] = overall

    return {
        "critic_state": critic_state,
        "run_phase": "evals",
    }


def telemetry_node(state: State) -> Dict[str, Any]:
    design_state = state.get("design_state") or {}
    plan_state = state.get("plan_state") or {}
    research_state = state.get("research_state") or {}
    critic_state = state.get("critic_state") or {}

    plan_summary = _coerce_str(plan_state.get("summary"), max_len=600) or ""
    research_summary = _coerce_str(research_state.get("summary"), max_len=600) or ""
    design_notes = _coerce_str_list(design_state.get("notes"), max_items=8, max_len=200)
    critic_notes = _coerce_str_list(critic_state.get("notes"), max_items=8, max_len=200)

    schema_desc = json.dumps(
        {
            "status": "completed",
            "telemetry": {
                "latency": {"p50_ms": 120, "p95_ms": 400},
                "error_rate": 0.02,
                "failures": {"recent": 0, "notes": "none"},
                "resource_util": {"cpu": 0.55, "memory": 0.60},
                "throughput": {"rps": 5},
                "cost": {"monthly_usd": 120.0},
            },
            "notes": ["brief telemetry rationale"],
        },
        ensure_ascii=False,
    )
    sys = SystemMessage(content=(
        "You infer runtime telemetry from the described system. Return JSON only:\n"
        f"{schema_desc}\n"
        "If uncertain, provide reasonable estimates; keep notes concise."
    ))

    prompt_lines = []
    if plan_summary:
        prompt_lines.append(f"Plan summary:\n{plan_summary}")
    if research_summary:
        prompt_lines.append(f"\nResearch summary:\n{research_summary}")
    if design_notes:
        prompt_lines.append("\nDesign notes:\n" + "\n".join(f"- {n}" for n in design_notes))
    if critic_notes:
        prompt_lines.append("\nCritic notes:\n" + "\n".join(f"- {n}" for n in critic_notes))
    prompt = "\n".join(prompt_lines) if prompt_lines else "No context provided."

    run_id = state.get("metadata", {}).get("run_id")
    raw = call_brain([sys, HumanMessage(content=prompt)], state=state, run_id=run_id, node="telemetry_node")
    parsed = json_only(raw) or {}
    telemetry = parsed.get("telemetry") if isinstance(parsed.get("telemetry"), dict) else {}
    notes = _coerce_str_list(parsed.get("notes"), max_items=8, max_len=200)
    status = _coerce_str(parsed.get("status"), max_len=16) or ("completed" if telemetry else "skipped")

    result = {
        "status": status,
        "telemetry": telemetry,
        "notes": notes,
    }
    
    # Store result in eval_state.telemetry for evals_agent to aggregate
    existing_eval_state = state.get("eval_state") or {}
    existing_eval_state["telemetry"] = result
    
    return {
        "eval_state": existing_eval_state,
    }


def scores_node(state: State) -> Dict[str, Any]:
    eval_state = state.get("eval_state") or {}
    telemetry = eval_state.get("telemetry") or {}
    plan_state = state.get("plan_state") or {}
    design_state = state.get("design_state") or {}
    critic_state = state.get("critic_state") or {}
    plan_summary = _coerce_str(plan_state.get("summary"), max_len=600) or ""
    design_notes = _coerce_str_list(design_state.get("notes"), max_items=8, max_len=200)
    critic_notes = _coerce_str_list(critic_state.get("notes"), max_items=8, max_len=200)
    schema_desc = json.dumps(
        {
            "status": "completed",
            "scores": {
                "latency": 0.8,
                "error_rate": 0.9,
                "failures": 0.95,
                "resource_util": 0.75,
                "throughput": 0.7,
                "cost": 0.6,
            },
            "notes": ["brief scoring rationale"],
        },
        ensure_ascii=False,
    )
    sys = SystemMessage(content=(
        "You score process/operational metrics using provided telemetry.\n"
        f"Return JSON only:\n{schema_desc}\n"
        "Scores are 0-1 (higher is better). Keep notes concise."
    ))

    prompt_lines = []
    prompt_lines.append("Telemetry (may be empty):")
    prompt_lines.append(json.dumps(telemetry or {}, ensure_ascii=False))
    if plan_summary:
        prompt_lines.append(f"\nPlan summary:\n{plan_summary}")
    if design_notes:
        prompt_lines.append("\nDesign notes:\n" + "\n".join(f"- {n}" for n in design_notes))
    if critic_notes:
        prompt_lines.append("\nCritic notes:\n" + "\n".join(f"- {n}" for n in critic_notes))
    prompt = "\n".join(prompt_lines)
    run_id = state.get("metadata", {}).get("run_id")
    raw = call_brain([sys, HumanMessage(content=prompt)], state=state, run_id=run_id, node="scores_node")
    parsed = json_only(raw) or {}
    scores = parsed.get("scores") if isinstance(parsed.get("scores"), dict) else {}
    notes = _coerce_str_list(parsed.get("notes"), max_items=8, max_len=200)
    status = _coerce_str(parsed.get("status"), max_len=16) or ("completed" if scores else "skipped")

    needs_attention = False
    for val in scores.values():
        try:
            if float(val) < 0.5:
                needs_attention = True
                break
        except (TypeError, ValueError):
            continue

    result = {
        "status": status,
        "scores": scores,
        "needs_attention": needs_attention,
        "notes": notes,
    }
    
    # Store result in eval_state.scores for evals_agent to aggregate
    existing_eval_state = state.get("eval_state") or {}
    existing_eval_state["scores"] = result
    
    return {
        "eval_state": existing_eval_state,
    }


def _build_architecture_json(state: State) -> Dict[str, Any]:

    design_state = state.get("design_state") or {}
    plan_state = state.get("plan_state") or {}
    diagram = {}
    if isinstance(design_state.get("diagram"), dict):
        diagram = design_state.get("diagram") or {}
    if isinstance(diagram.get("diagram"), dict):
        # Some generators may wrap diagram payload
        diagram = diagram.get("diagram") or diagram

    elements: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []

    # Use diagram nodes/edges if they look valid
    nodes_from_diag = diagram.get("nodes") if isinstance(diagram, dict) else None
    edges_from_diag = diagram.get("edges") if isinstance(diagram, dict) else None

    if isinstance(nodes_from_diag, list):
        for node in nodes_from_diag:
            if not isinstance(node, dict):
                continue
            node_id = _coerce_str(node.get("id"), max_len=64)
            label = _coerce_str(node.get("label") or node.get("name"), max_len=120) or node_id
            kind = _coerce_str(node.get("type") or node.get("kind"), max_len=32) or "Component"
            if not node_id or not label:
                continue
            entry: dict[str, Any] = {"id": node_id, "label": label, "kind": kind}
            desc = _coerce_str(node.get("description"), max_len=280)
            if desc:
                entry["description"] = desc
            tech = _coerce_str(node.get("technology"), max_len=80)
            if tech:
                entry["technology"] = tech
            elements.append(entry)

    if isinstance(edges_from_diag, list):
        for edge in edges_from_diag:
            if not isinstance(edge, dict):
                continue
            source = _coerce_str(edge.get("source"), max_len=64)
            target = _coerce_str(edge.get("target"), max_len=64)
            label = _coerce_str(edge.get("label"), max_len=120)
            if not source or not target:
                continue
            relations.append(
                {
                    "source": source,
                    "target": target,
                    "label": label or "relation",
                }
            )
    if not elements:
        comps = design_state.get("components", {}).get("components") or []
        seen_ids: set[str] = set()
        for comp in comps:
            if not isinstance(comp, dict):
                continue
            comp_id = _coerce_str(comp.get("id"), max_len=64)
            comp_name = _coerce_str(comp.get("name"), max_len=120) or comp_id
            comp_type = _coerce_str(comp.get("type"), max_len=32) or "Component"
            if not comp_id or comp_id in seen_ids:
                continue
            seen_ids.add(comp_id)
            elements.append(
                {
                    "id": comp_id,
                    "label": comp_name,
                    "kind": comp_type,
                }
            )

    if not relations and elements:
        # Create simple flow relations based on plan steps order
        steps = plan_state.get("steps") or []
        ids = [el.get("id") for el in elements if isinstance(el, dict)]
        if isinstance(steps, list):
            prev = None
            for step in steps:
                if not isinstance(step, dict):
                    continue
                title = _coerce_str(step.get("title"), max_len=80) or "step"
                # Link consecutive unique elements if possible
                if len(ids) >= 2:
                    for idx in range(len(ids) - 1):
                        src = ids[idx]
                        tgt = ids[idx + 1]
                        relations.append(
                            {
                                "source": src,
                                "target": tgt,
                                "label": title,
                            }
                        )
                        break
                elif prev:
                    relations.append({"source": prev, "target": ids[0], "label": title})
                prev = ids[0] if ids else prev

    if not elements:
        return {}

    return {
        "elements": elements,
        "relations": relations,
    }


def final_judgement_node(state: State) -> Dict[str, Any]:
    plan_state = state.get("plan_state") or {}
    plan_scope = state.get("plan_scope") or {}
    research_state = state.get("research_state") or {}
    design_state = state.get("design_state") or {}
    critic_state = state.get("critic_state") or {}
    eval_state = state.get("eval_state") or {}

    goal = _coerce_str(state.get("goal"), max_len=400) or "No goal provided."
    plan_summary = _coerce_str(plan_state.get("summary"), max_len=800) or ""
    plan_steps = plan_state.get("steps") if isinstance(plan_state.get("steps"), list) else []

    # Research highlights/citations
    nodes = research_state.get("nodes") or {}
    def _collect(list_key: str) -> list[str]:
        out: list[str] = []
        for res in nodes.values():
            if isinstance(res, dict):
                out.extend(_coerce_str_list(res.get(list_key), max_items=12, max_len=320))
        return _limit_strings(out, limit=12)
    research_highlights = _collect("highlights")
    research_risks = _collect("risks")
    research_citations: list[dict] = []
    for res in nodes.values():
        if isinstance(res, dict):
            cites = res.get("citations") or []
            if isinstance(cites, list):
                research_citations.extend([c for c in cites if isinstance(c, dict)])
    research_citations = research_citations[:12]

    # Design components/costs/notes
    components = design_state.get("components", {}).get("components") or []
    costs = design_state.get("costs", {})
    design_notes = _coerce_str_list(design_state.get("notes"), max_items=8, max_len=200)

    # Critic notes
    critic_notes = _coerce_str_list(critic_state.get("notes"), max_items=8, max_len=200)

    # Evals telemetry/scores
    telemetry = eval_state.get("telemetry", {}).get("telemetry") if isinstance(eval_state.get("telemetry"), dict) else {}
    scores = eval_state.get("scores", {}).get("scores") if isinstance(eval_state.get("scores"), dict) else {}
    needs_attention = bool(eval_state.get("needs_attention") or eval_state.get("scores", {}).get("needs_attention"))

    # Architecture JSON
    architecture_json = _build_architecture_json(state)

    # Design brief
    design_brief_parts = []
    if plan_summary:
        design_brief_parts.append(f"Plan: {plan_summary}")
    if components:
        design_brief_parts.append(f"Components: {min(len(components),5)} key components identified.")
    if costs:
        design_brief_parts.append("Costs estimated.")
    if critic_notes:
        design_brief_parts.append("Critic notes captured.")
    design_brief = " ".join(design_brief_parts) or "Design completed; see details below."

    lines: list[str] = []

    # Section 1: Plan
    lines.append("## Plan")
    if plan_summary:
        lines.append(plan_summary)
    if plan_steps:
        # Condense steps into brief numbered list
        step_items = []
        for i, step in enumerate(plan_steps[:5], 1):
            if not isinstance(step, dict):
                continue
            title = _coerce_str(step.get("title"), max_len=80) or "Step"
            step_items.append(f"{i}. **{title}**")
        if step_items:
            lines.append("\n**Key Steps:**")
            lines.extend(step_items)
    if not plan_summary and not plan_steps:
        lines.append("*No plan details available.*")

    # Section 2: Research Notes (critical findings only)
    lines.append("\n## Research Notes")
    has_research = False
    if research_highlights:
        has_research = True
        lines.append("**Key Findings:**")
        for h in research_highlights[:4]:
            lines.append(f"- {h}")
    if research_risks:
        has_research = True
        lines.append("\n**Risks Identified:**")
        for r in research_risks[:3]:
            lines.append(f"- {r}")
    if research_citations:
        has_research = True
        lines.append("\n**Sources:**")
        for c in research_citations[:4]:
            url = _coerce_str(c.get("url"), max_len=160) or ""
            title = _coerce_str(c.get("title"), max_len=80) or "Source"
            lines.append(f"- [{title}]({url})" if url else f"- {title}")
    if not has_research:
        lines.append("*No research notes available.*")

    # Section 3: Design Overview (components + costs table)
    lines.append("\n## Design Overview")
    has_design = False
    if components:
        has_design = True
        lines.append("**Components:**")
        for comp in components[:6]:
            if not isinstance(comp, dict):
                continue
            name = _coerce_str(comp.get("name"), max_len=80) or _coerce_str(comp.get("id"), max_len=40) or "Component"
            ctype = _coerce_str(comp.get("type"), max_len=24) or ""
            lines.append(f"- **{name}**" + (f" ({ctype})" if ctype else ""))
    
    # Format cost estimates from the structured costs dict
    cost_estimates = costs.get("estimates", []) if isinstance(costs, dict) else []
    cost_total = costs.get("total", {}) if isinstance(costs, dict) else {}
    if cost_estimates:
        has_design = True
        lines.append("\n**Cost Estimates:**")
        lines.append("")
        lines.append("| Component | Monthly | One-time |")
        lines.append("|-----------|---------|----------|")
        for est in cost_estimates[:8]:
            if not isinstance(est, dict):
                continue
            name = _coerce_str(est.get("name"), max_len=40) or "Component"
            monthly = est.get("monthly_usd", 0)
            one_time = est.get("one_time_usd", 0)
            monthly_str = f"${monthly:,.0f}/mo" if monthly else "-"
            one_time_str = f"${one_time:,.0f}" if one_time else "-"
            lines.append(f"| {name} | {monthly_str} | {one_time_str} |")
        # Add totals row
        total_monthly = cost_total.get("monthly_usd", 0)
        total_one_time = cost_total.get("one_time_usd", 0)
        if total_monthly or total_one_time:
            lines.append(f"| **Total** | **${total_monthly:,.0f}/mo** | **${total_one_time:,.0f}** |")
    if not has_design:
        lines.append("*No design details available.*")

    # Section 4: Critic Notes (quality assessment)
    lines.append("\n## Critic Notes")
    if critic_notes:
        for n in critic_notes[:4]:
            lines.append(f"- {n}")
    else:
        lines.append("*No critic notes available.*")

    # Section 5: Evaluation Outcomes
    lines.append("\n## Evaluation Outcomes")
    has_evals = False
    if scores:
        has_evals = True
        lines.append("**Scores:**")
        lines.append("")
        lines.append("| Metric | Score |")
        lines.append("|--------|-------|")
        for k, v in scores.items():
            score_val = f"{float(v):.2f}" if isinstance(v, (int, float)) else str(v)
            lines.append(f"| {k} | {score_val} |")
    if needs_attention:
        has_evals = True
        lines.append("\n**Attention Required:** Some scores are below threshold; review recommended.")
    if telemetry:
        has_evals = True
        lines.append("\n**Telemetry:**")
        for k, v in list(telemetry.items())[:4]:
            lines.append(f"- {k}: {v}")
    if not has_evals:
        lines.append("*No evaluation data available.*")

    markdown_output = "\n".join(lines)

    # Update eval_state final_judgement for routing
    updated_eval_state = dict(eval_state)
    updated_eval_state["final_judgement"] = {"status": "completed"}

    return {
        "eval_state": updated_eval_state,
        "architecture_json": architecture_json,
        "design_brief": design_brief,
        "output": markdown_output,
        "messages": [AIMessage(content=markdown_output)],
    }


def evals_agent(state: State) -> Dict[str, any]:
    existing = state.get("eval_state")
    eval_state = _initial_eval_state(existing)

    # Get results from subnodes (they update state directly via graph edges)
    telemetry_result = eval_state.get("telemetry", {})
    scores_result = eval_state.get("scores", {})
    final_result = eval_state.get("final_judgement", {})
    
    # Check status of subnodes
    telemetry_status = telemetry_result.get("status", "").lower() if isinstance(telemetry_result, dict) else ""
    scores_status = scores_result.get("status", "").lower() if isinstance(scores_result, dict) else ""
    final_status = final_result.get("status", "").lower() if isinstance(final_result, dict) else ""
    
    telemetry_completed = telemetry_status == "completed" or telemetry_status == "skipped"
    scores_completed = scores_status == "completed" or scores_status == "skipped"
    final_completed = final_status == "completed" or final_status == "skipped"
    
    # If subnodes are not all complete, routing will handle it
    # This function only aggregates when all are done
    if not (telemetry_completed and scores_completed and final_completed):
        # Still update eval_state with what we have
        if telemetry_completed:
            eval_state["telemetry"] = telemetry_result
        if scores_completed:
            eval_state["scores"] = scores_result
            eval_state["needs_attention"] = bool(scores_result.get("needs_attention"))
        if final_completed:
            eval_state["final_judgement"] = final_result
        
        # Return minimal updates - routing will handle next step
        return {
            "eval_state": eval_state,
        }
    
    # All subnodes are complete - aggregate results
    eval_state["telemetry"] = telemetry_result
    eval_state["scores"] = scores_result
    eval_state["needs_attention"] = bool(scores_result.get("needs_attention"))
    eval_state["final_judgement"] = final_result
    
    # Aggregate notes
    for result in [telemetry_result, scores_result, final_result]:
        if isinstance(result, dict):
            notes = result.get("notes")
            if isinstance(notes, list):
                for note in notes:
                    eval_state["notes"] = _append_eval_note(eval_state.get("notes", []), note)
            elif notes:
                eval_state["notes"] = _append_eval_note(eval_state.get("notes", []), notes)

    # Determine overall status
    statuses = [telemetry_status, scores_status, final_status]
    lowered = [s.lower() for s in statuses if s]
    if any(s == "completed" for s in lowered):
        overall = "completed"
    elif any(s == "pending" for s in lowered):
        overall = "pending"
    elif lowered:
        overall = "skipped"
    else:
        overall = eval_state.get("status") or "pending"
    eval_state["status"] = overall

    return {
        "eval_state": eval_state,
        "run_phase": "done",
    }
