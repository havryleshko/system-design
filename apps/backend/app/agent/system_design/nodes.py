from typing import Any, Dict, Optional, Sequence
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from .state import State
try:  
    from langchain_openai import ChatOpenAI  
except Exception:  
    ChatOpenAI = None  

from functools import lru_cache
import json, os, math
from datetime import datetime, timezone

try:  
    from langgraph.types import interrupt, Command  # type: ignore
except Exception:
    interrupt = None  
    Command = None  
import logging
import requests

# Supabase client is optional; guard import so graph can load without the package present.
try:
    from supabase import create_client  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    create_client = None

try:
    from app.storage.memory import add_event, record_node_tokens, get_total_tokens
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

    def get_total_tokens(run_id: str) -> int:
        return 0
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
    if ChatOpenAI is None:
        raise RuntimeError("langchain-openai is not installed. Install backend requirements.")
    model_name = model or os.getenv("CHAT_OPENAI_MODEL", "gpt-4o-mini")
    # Max output tokens is a practical guardrail; total budget is enforced separately.
    max_out = int(os.getenv("CHAT_OPENAI_MAX_OUTPUT_TOKENS", "1200"))
    temperature = float(os.getenv("CHAT_OPENAI_TEMPERATURE", "0.2"))
    return ChatOpenAI(model=model_name, max_tokens=max_out, temperature=temperature)

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

    # Hard budget guardrail (MVP): abort runs that exceed max total tokens.
    limit = int(os.getenv("RUN_MAX_TOTAL_TOKENS", "20000") or "20000")
    current = get_total_tokens(run_id)
    if limit > 0 and current > limit:
        raise RuntimeError(f"Token budget exceeded: {current} > {limit}")



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
                # Reset subnode state to allow retry (tests expect cleared state, not just pending flags)
            return {
                "planner_state": planner_state,
                    "plan_scope": {},
                    "plan_state": {},
                "metadata": updated_meta,
                "run_phase": "planner",
            }
    
    # Finalize and record memory
    summary = _coerce_str(plan_state.get("summary"), max_len=600)
    _record_final_plan_memory(state, summary)
    
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

    # Clarifier is required for blocking issues (e.g. missing goal)
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
            "high_level_objective": "One sentence summarizing the main goal",
            "intermediate_milestones": [
                "Milestone 1: Clear checkpoint that can be verified",
                "Milestone 2: Next major deliverable",
                "Milestone 3: Final integration checkpoint"
            ],
            "atomic_tasks": [
                {
                    "id": "task-1",
                    "task": "Specific action that can be checked as done/not done",
                    "milestone": "milestone-1",
                    "verifiable_output": "What artifact or state proves this is done"
                }
            ],
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
        "You are a senior agentic systems planner. Return JSON only matching this schema:\n"
        f"{schema_desc}\n\n"
        "CRITICAL RULES FOR GOAL DECOMPOSITION:\n"
        "1. high_level_objective: One clear sentence describing what success looks like\n"
        "2. intermediate_milestones: 2-4 checkpoints that mark significant progress (each must be verifiable)\n"
        "3. atomic_tasks: Break down into specific tasks that can be CHECKED as done/not done\n"
        "   - Each task must have a verifiable_output (artifact, state change, or measurable result)\n"
        "   - Tasks should be small enough to complete in one agent action\n"
        "4. steps: High-level implementation steps (keep at most 5)\n"
        "5. risks: Notable risks or blockers\n\n"
        "Focus on VERIFIABILITY - every task and milestone must be objectively checkable."
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

    # Extract goal decomposition fields
    high_level_objective = _coerce_str(parsed.get("high_level_objective"), max_len=200) or goal
    intermediate_milestones = _coerce_str_list(parsed.get("intermediate_milestones"), max_items=5, max_len=150)
    
    # Normalize atomic tasks
    raw_atomic_tasks = parsed.get("atomic_tasks") or []
    atomic_tasks: list[dict[str, Any]] = []
    for task in raw_atomic_tasks:
        if isinstance(task, dict):
            task_entry = {
                "id": _coerce_str(task.get("id"), max_len=32) or f"task-{len(atomic_tasks)+1}",
                "task": _coerce_str(task.get("task"), max_len=200) or "Task",
                "verifiable_output": _coerce_str(task.get("verifiable_output"), max_len=150) or "",
            }
            milestone = _coerce_str(task.get("milestone"), max_len=40)
            if milestone:
                task_entry["milestone"] = milestone
            atomic_tasks.append(task_entry)
        elif isinstance(task, str):
            atomic_tasks.append({
                "id": f"task-{len(atomic_tasks)+1}",
                "task": _coerce_str(task, max_len=200) or "Task",
                "verifiable_output": "",
            })
    atomic_tasks = atomic_tasks[:10]  # Limit to 10 atomic tasks

    plan_state_data = {
        "status": "completed",
        "high_level_objective": high_level_objective,
        "intermediate_milestones": intermediate_milestones,
        "atomic_tasks": atomic_tasks,
        "steps": normalized_steps,
        "summary": summary_text,
        "issues": issues,
        "risks": risks,
        "quality": quality,
    }
    
    notes: list[str] = []
    if normalized_steps:
        notes.append(f"Generated {len(normalized_steps)} plan step(s)")
    if atomic_tasks:
        notes.append(f"Defined {len(atomic_tasks)} atomic task(s)")
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


def pattern_selector_node(state: State) -> Dict[str, Any]:
    run_id = (state.get("metadata") or {}).get("run_id") or ""
    goal = _coerce_str(state.get("goal"), max_len=500) or ""
    plan_state = state.get("plan_state") or {}
    plan_summary = _coerce_str(plan_state.get("summary"), max_len=500) or ""
    
    notes: list[str] = []
    selected_patterns: list[dict] = []
    
    patterns_path = os.path.join(os.path.dirname(__file__), "agentic_patterns.json")
    domain_templates_path = os.path.join(os.path.dirname(__file__), "domain_templates.json")
    
    try:
        with open(patterns_path, "r") as f:
            patterns_data = json.load(f)
        patterns = patterns_data.get("patterns", [])
    except Exception as e:
        logger.warning(f"Failed to load agentic_patterns.json: {e}")
        patterns = []
        notes.append(f"Failed to load patterns: {str(e)[:100]}")

    try:
        with open(domain_templates_path, "r") as f:
            domain_data = json.load(f)
        domain_templates = domain_data.get("templates", [])
    except Exception as e:
        logger.warning(f"Failed to load domain_templates.json: {e}")
        domain_templates = []
    
    if not patterns:
        result = {
            "status": "skipped",
            "selected_patterns": [],
            "notes": notes or ["No patterns available"],
        }
        existing_research_state = state.get("research_state") or {}
        existing_nodes = existing_research_state.get("nodes") or {}
        existing_nodes["pattern_selector"] = result
        return {
            "research_state": {
                **existing_research_state,
                "nodes": existing_nodes,
                "selected_patterns": [],
            }
        }

    pattern_summaries = []
    for p in patterns:
        summary = f"- **{p.get('name', 'Unknown')}** (id: {p.get('id', '')}): {p.get('description', '')[:200]}"
        pattern_summaries.append(summary)
    
    patterns_text = "\n".join(pattern_summaries)
 
    domain_hints = []
    goal_lower = goal.lower()
    for template in domain_templates:
        keywords = template.get("keywords", [])
        if any(kw in goal_lower for kw in keywords):
            domain_hints.append({
                "domain": template.get("name", ""),
                "primary_patterns": template.get("primary_patterns", []),
            })
    
    domain_hint_text = ""
    if domain_hints:
        hints = [f"- {h['domain']}: suggests patterns {h['primary_patterns']}" for h in domain_hints[:2]]
        domain_hint_text = f"\n\nDomain hints based on keywords:\n" + "\n".join(hints)
    
    # 3. Build LLM prompt
    prompt = f"""You are selecting agentic architecture patterns for a system design task.

## Available Patterns:
{patterns_text}
{domain_hint_text}

## User's Goal:
{goal}

## Plan Summary:
{plan_summary or "No plan summary available"}

## Task:
Select the 2-3 MOST relevant patterns for this goal. Consider:
1. The nature of the task (reasoning, tool use, multi-agent, etc.)
2. The complexity and structure needed
3. Whether the task requires iteration, planning, or parallel work

## Output Format:
Return a JSON array of pattern IDs (strings), ordered by relevance.
Example: ["react", "tool-use"]

Only return the JSON array, no other text."""

    # 4. Call LLM
    try:
        brain = make_brain()
        messages = [
            SystemMessage(content="You are an expert at selecting appropriate agentic patterns for system design tasks. Return only valid JSON."),
            HumanMessage(content=prompt),
        ]
        response = brain.invoke(messages)
        response_text = response.content.strip()
        
        # Track tokens
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("token_usage", {})
            record_node_tokens(
                run_id,
                "pattern_selector_node",
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
            )
        
        # Parse response - handle markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        
        selected_ids = json.loads(response_text)
        if not isinstance(selected_ids, list):
            selected_ids = []
        
        # 5. Get full pattern details for selected patterns
        for pattern_id in selected_ids[:3]:  # Max 3 patterns
            for p in patterns:
                if p.get("id") == pattern_id:
                    selected_patterns.append({
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "description": p.get("description"),
                        "when_to_use": p.get("when_to_use", [])[:3],
                        "typical_agents": p.get("typical_agents", []),
                        "mermaid_template": p.get("mermaid_template", ""),
                    })
                    break
        
        notes.append(f"Selected {len(selected_patterns)} patterns: {[p['name'] for p in selected_patterns]}")
        
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}")
        notes.append(f"JSON parse error, using fallback patterns")
        # Fallback to react + tool-use as safe defaults
        for p in patterns:
            if p.get("id") in ["react", "tool-use"]:
                selected_patterns.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "when_to_use": p.get("when_to_use", [])[:3],
                    "typical_agents": p.get("typical_agents", []),
                    "mermaid_template": p.get("mermaid_template", ""),
                })
    except Exception as e:
        logger.warning(f"LLM call failed in pattern_selector_node: {e}")
        notes.append(f"LLM error: {str(e)[:100]}")
        # Fallback to domain-hinted patterns or defaults
        fallback_ids = []
        if domain_hints:
            for hint in domain_hints:
                fallback_ids.extend(hint.get("primary_patterns", []))
        if not fallback_ids:
            fallback_ids = ["react", "tool-use"]
        
        for p in patterns:
            if p.get("id") in fallback_ids[:3]:
                selected_patterns.append({
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description"),
                    "when_to_use": p.get("when_to_use", [])[:3],
                    "typical_agents": p.get("typical_agents", []),
                    "mermaid_template": p.get("mermaid_template", ""),
                })
    
    # Explainability fields (for post-hoc reasoning trace)
    what = f"Selected {len(selected_patterns)} agentic pattern(s)"
    why_parts: list[str] = []
    if domain_hints:
        hint_domains = [h.get("domain") for h in domain_hints if isinstance(h, dict) and h.get("domain")]
        if hint_domains:
            why_parts.append(f"Goal keywords matched domains: {', '.join(hint_domains[:2])}")
    if plan_summary:
        why_parts.append("Plan summary used as selection context")
    if selected_patterns:
        why_parts.append(f"Chosen patterns: {', '.join([p.get('name','') for p in selected_patterns if isinstance(p, dict) and p.get('name')][:3])}")
    why = "; ".join([p for p in why_parts if p]) or None

    alternatives_considered: list[dict] = []
    if domain_hints:
        suggested: list[str] = []
        for hint in domain_hints[:2]:
            if isinstance(hint, dict):
                for pid in hint.get("primary_patterns", [])[:5]:
                    if pid and pid not in suggested:
                        suggested.append(pid)
        chosen_ids = {p.get("id") for p in selected_patterns if isinstance(p, dict)}
        for pid in suggested:
            if pid and pid not in chosen_ids:
                alternatives_considered.append(
                    {"id": pid, "reason": "Suggested by domain template keywords but not selected"}
                )
        alternatives_considered = alternatives_considered[:6]

    result = {
        "status": "completed" if selected_patterns else "skipped",
        "selected_patterns": selected_patterns,
        "notes": notes,
        "what": what,
        "why": why,
        "alternatives_considered": alternatives_considered or None,
    }
    
    # Store result in research_state.nodes for research_agent to aggregate
    existing_research_state = state.get("research_state") or {}
    existing_nodes = existing_research_state.get("nodes") or {}
    existing_nodes["pattern_selector"] = result
    
    return {
        "research_state": {
            **existing_research_state,
            "nodes": existing_nodes,
            "selected_patterns": selected_patterns,
        },
        "selected_patterns": selected_patterns,
    }


def research_agent(state: State) -> Dict[str, any]:
    existing = state.get("research_state")
    research_state = _initial_research_state(existing)
    
    goal = _coerce_str(state.get("goal"), max_len=500) or ""
    nodes = research_state.get("nodes") or {}
    in_graph_mode = isinstance(state.get("run_phase"), str) and bool(state.get("run_phase"))

    if not in_graph_mode:
        if not nodes:
            if not goal:
                nodes = {
                    "knowledge_base": {"status": "skipped", "notes": "Goal missing"},
                    "github_api": {"status": "skipped", "notes": "Goal missing"},
                    "web_search": {"status": "skipped", "notes": "Goal missing"},
                }
            else:
                def _as_payload(key: str, out: Any) -> dict[str, Any]:
                    if isinstance(out, dict) and isinstance(out.get("research_state"), dict):
                        rs = out.get("research_state") or {}
                        nd = rs.get("nodes") or {}
                        candidate = nd.get(key)
                        if isinstance(candidate, dict):
                            return candidate
                    return out if isinstance(out, dict) else {"status": "skipped", "notes": f"{key} non-dict result"}

                kb_out = knowledge_base_node(state)
                gh_out = github_api_node(state)
                web_out = web_search_node(state)
                nodes = {
                    "knowledge_base": _as_payload("knowledge_base", kb_out),
                    "github_api": _as_payload("github_api", gh_out),
                    "web_search": _as_payload("web_search", web_out),
                }
            research_state["nodes"] = nodes
    
    # Graph-mode uses pattern_selector_node + other subnodes; direct-call mode may omit pattern selector.
    pattern_result = nodes.get("pattern_selector", {}) if isinstance(nodes, dict) else {}
    kb_result = nodes.get("knowledge_base", {}) if isinstance(nodes, dict) else {}
    github_result = nodes.get("github_api", {}) if isinstance(nodes, dict) else {}
    web_result = nodes.get("web_search", {}) if isinstance(nodes, dict) else {}

    pattern_status = pattern_result.get("status", "").lower() if isinstance(pattern_result, dict) else ""
    kb_status = kb_result.get("status", "").lower() if isinstance(kb_result, dict) else ""
    github_status = github_result.get("status", "").lower() if isinstance(github_result, dict) else ""
    web_status = web_result.get("status", "").lower() if isinstance(web_result, dict) else ""

    pattern_completed = pattern_status == "completed" or pattern_status == "skipped" or (not in_graph_mode)
    kb_completed = kb_status == "completed" or kb_status == "skipped"
    github_completed = github_status == "completed" or github_status == "skipped"
    web_completed = web_status == "completed" or web_status == "skipped"

    if not (pattern_completed and kb_completed and github_completed and web_completed):
        # Routing will handle next step in graph-mode.
        return {"research_state": research_state}

    # All subnodes are complete - aggregate results
    node_outputs = {
        "pattern_selector_node": pattern_result,
        "knowledge_base_node": kb_result,
        "github_api_node": github_result,
        "web_search_node": web_result,
    }

    # Store all node outputs (keep pattern selector in graph-mode for routing/debugging)
    aggregated_nodes: dict[str, Any] = {
        "knowledge_base": kb_result,
        "github_api": github_result,
        "web_search": web_result,
    }
    if in_graph_mode:
        aggregated_nodes["pattern_selector"] = pattern_result
    research_state["nodes"] = aggregated_nodes

    # Preserve selected_patterns from pattern_selector_node (graph-mode)
    if in_graph_mode and isinstance(pattern_result, dict):
        selected_patterns = pattern_result.get("selected_patterns", [])
        if selected_patterns:
            research_state["selected_patterns"] = selected_patterns
    
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
        "needs_attention": bool(data.get("needs_attention")) if data.get("needs_attention") is not None else False,
        "notes": _coerce_str_list(data.get("notes"), max_items=8, max_len=200),
    }


def _initial_design_state(existing: Optional[dict[str, Any]]) -> dict[str, Any]:
    data = existing if isinstance(existing, dict) else {}
    return {
        "status": _coerce_str(data.get("status")) or "pending",
        "architecture": data.get("architecture") or {},
        "output": data.get("output") or {},
        "notes": _coerce_str_list(data.get("notes"), max_items=8, max_len=160),
    }


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


def architecture_generator_node(state: State) -> Dict[str, Any]:
    run_id = (state.get("metadata") or {}).get("run_id") or ""
    goal = _coerce_str(state.get("goal"), max_len=500) or "System"
    plan_state = state.get("plan_state") or {}
    research_state = state.get("research_state") or {}
    
    # Get selected patterns from research phase
    selected_patterns = state.get("selected_patterns") or research_state.get("selected_patterns") or []
    
    # Get research highlights
    research_highlights = research_state.get("highlights", [])[:5]
    research_citations = research_state.get("citations", [])[:3]
    
    notes: list[str] = []
    architecture: dict = {}
    
    # Load domain templates for additional context
    domain_templates_path = os.path.join(os.path.dirname(__file__), "domain_templates.json")
    domain_template = None
    try:
        with open(domain_templates_path, "r") as f:
            domain_data = json.load(f)
        templates = domain_data.get("templates", [])
        
        # Find matching domain template based on keywords
        goal_lower = goal.lower()
        for template in templates:
            keywords = template.get("keywords", [])
            if any(kw in goal_lower for kw in keywords):
                domain_template = template
                break
    except Exception as e:
        logger.warning(f"Failed to load domain_templates.json: {e}")
    
    # Build patterns context for prompt
    patterns_context = ""
    if selected_patterns:
        pattern_texts = []
        for p in selected_patterns[:3]:
            pattern_text = f"""### {p.get('name', 'Pattern')}
{p.get('description', '')}

When to use: {', '.join(p.get('when_to_use', [])[:3])}

Typical agents:
{json.dumps(p.get('typical_agents', []), indent=2)}
"""
            pattern_texts.append(pattern_text)
        patterns_context = "\n".join(pattern_texts)
    
    # Build domain template context
    domain_context = ""
    if domain_template:
        domain_context = f"""
## Domain Template: {domain_template.get('name', '')}
{domain_template.get('description', '')}

Typical architecture for this domain:
{json.dumps(domain_template.get('typical_architecture', {}), indent=2)}
"""
    
    # Build research context
    research_context = ""
    if research_highlights:
        research_context = "\n## Research Findings:\n" + "\n".join([f"- {h}" for h in research_highlights[:5]])
    
    # Build the prompt
    prompt = f"""You are designing an agentic architecture for the following goal.

## Goal:
{goal}

## Plan Summary:
{plan_state.get('summary', 'No plan summary available')}

## Selected Patterns:
{patterns_context or "No patterns selected - use your best judgment"}
{domain_context}
{research_context}

## Output Schema:
Generate a complete architecture as JSON with this structure:
{{
    "architecture_class": "hierarchical_orchestrator|supervisor_worker|planner_executor_evaluator_loop|hybrid",
    "architecture_class_reason": "Required only if architecture_class=hybrid; explain why it's hybrid",
    "tradeoffs": [
        {{
            "decision": "Decision being made",
            "alternatives": ["Option A", "Option B"],
            "why": "Why the chosen option fits this goal/constraints"
        }}
    ],
    "overview": "Brief 2-3 sentence description of the architecture",
    "agents": [
        {{
            "id": "unique_id",
            "name": "GoalSpecificAgentName",
            "responsibility": "What this agent does",
            "tools": ["tool1", "tool2"],
            "subagents": ["child_agent_id_1", "child_agent_id_2"],
            "inputs": ["What this agent consumes (messages, artifacts, events)"],
            "outputs": ["What this agent produces (artifacts, decisions, events)"],
            "memory_owned": [
                {{
                    "type": "short_term|long_term|episodic|semantic",
                    "purpose": "What this memory is for",
                    "implementation": "Concrete implementation hint (e.g., Redis, Postgres, vector store)"
                }}
            ],
            "failure_modes": ["Failure mode 1", "Failure mode 2"],
            "safeguards": ["Safeguard 1", "Safeguard 2"],
            "degrades_to": "How the system behaves when this agent/tooling fails (fallback mode)"
        }}
    ],
    "tools": [
        {{
            "id": "tool_id",
            "name": "Tool Name",
            "type": "api|db|llm|search|file|code|other",
            "io_schema": "{{input}} -> {{output}}",
            "failure_handling": "How to handle failures"
        }}
    ],
    "interactions": [
        {{
            "source": "agent_or_tool_id",
            "target": "agent_or_tool_id",
            "kind": "delegates|reviews|aggregates|routes|requests|returns|tool_call|reads|writes|notifies",
            "label": "Optional short human label shown on the edge"
        }}
    ],
    "memory": {{
        "short_term": {{"purpose": "...", "implementation": "..."}},
        "long_term": {{"purpose": "...", "implementation": "..."}}
    }},
    "control_loop": {{
        "flow": "START -> Agent1 -> Agent2 -> END",
        "termination_conditions": ["condition1", "condition2"]
    }},
    "bounded_autonomy": {{
        "constraints": [
            {{"constraint": "Max steps", "value": "20", "action_on_breach": "Terminate"}}
        ],
        "permission_gates": ["actions requiring approval"],
        "human_in_loop": ["scenarios requiring human review"]
    }},
    "implementation_notes": ["Note 1", "Note 2"],
    "start_simple_recommendation": "Recommendation for MVP implementation"
}}

## CRITICAL RULES:
1. Agent names MUST be goal-specific (e.g., "EmailTriager", "CodeReviewer", "ResearchSynthesizer")
2. DO NOT use generic names like "Planner", "Executor", "Critic", "Agent", "Worker"
3. Include at least 2 agents with distinct responsibilities
4. Tools should be specific to the goal (e.g., "gmail_api", "github_search", not just "api")
5. The architecture should directly address the user's goal
6. `subagents` MUST be a list of agent IDs (strings), not nested objects
7. `interactions[].source/target` MUST reference existing IDs from `agents[].id` or `tools[].id`
8. Include enough interactions to represent the true topology (fan-out/fan-in, routing, loops) — avoid a single linear chain unless the system is truly linear
9. Every agent MUST include: inputs[], outputs[], memory_owned[], failure_modes[], safeguards[], degrades_to.
10. `architecture_class` MUST be one of the allowed enum values; if `hybrid`, provide `architecture_class_reason`.

Return ONLY the JSON object, no markdown code blocks or other text."""

    # Call LLM with retry logic
    max_retries = 2
    architecture: dict[str, Any] = {}
    for attempt in range(max_retries + 1):
        try:
            brain = make_brain()
            messages = [
                SystemMessage(content="You are an expert system architect specializing in agentic AI systems. Generate precise, goal-specific architectures. Return only valid JSON."),
                HumanMessage(content=prompt),
            ]
            response = brain.invoke(messages)
            response_text = response.content.strip()
            
            # Track tokens
            if hasattr(response, "response_metadata"):
                usage = response.response_metadata.get("token_usage", {})
                record_node_tokens(
                    run_id,
                    "architecture_generator_node",
                    usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0),
                    usage.get("total_tokens", 0),
                )
            
            # Parse response - handle markdown code blocks
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            
            architecture = json.loads(response_text)
            
            # Validate architecture
            validation_errors = []
            agents = architecture.get("agents", [])
            tools = architecture.get("tools", [])
            interactions = architecture.get("interactions", [])
            arch_class = architecture.get("architecture_class")
            arch_class_reason = architecture.get("architecture_class_reason")
            tradeoffs = architecture.get("tradeoffs", [])
            
            if len(agents) < 2:
                validation_errors.append("Architecture must have at least 2 agents")

            allowed_arch_classes = {
                "hierarchical_orchestrator",
                "supervisor_worker",
                "planner_executor_evaluator_loop",
                "hybrid",
            }
            if arch_class not in allowed_arch_classes:
                validation_errors.append(
                    "architecture_class must be one of: hierarchical_orchestrator|supervisor_worker|planner_executor_evaluator_loop|hybrid"
                )
            if arch_class == "hybrid" and not isinstance(arch_class_reason, str):
                validation_errors.append("architecture_class_reason is required when architecture_class=hybrid")

            if not isinstance(tradeoffs, list) or not tradeoffs:
                validation_errors.append("tradeoffs must be a non-empty list of explicit trade-offs")
            else:
                for t in tradeoffs[:20]:
                    if not isinstance(t, dict):
                        validation_errors.append("tradeoffs entries must be objects")
                        break
                    if not t.get("decision") or not t.get("why") or not isinstance(t.get("alternatives"), list):
                        validation_errors.append("tradeoffs entries must include decision, alternatives[], and why")
                        break
            
            # Check for generic names
            generic_names = {"planner", "executor", "critic", "agent", "worker", "coordinator"}
            for agent in agents:
                name = (agent.get("name") or "").lower()
                if name in generic_names:
                    validation_errors.append(f"Agent name '{agent.get('name')}' is too generic")
            for agent in agents:
                if not isinstance(agent, dict):
                    continue
                if not isinstance(agent.get("inputs"), list):
                    validation_errors.append(f"Agent '{agent.get('id')}' missing inputs[]")
                if not isinstance(agent.get("outputs"), list):
                    validation_errors.append(f"Agent '{agent.get('id')}' missing outputs[]")
                if not isinstance(agent.get("memory_owned"), list):
                    validation_errors.append(f"Agent '{agent.get('id')}' missing memory_owned[]")
                if not isinstance(agent.get("failure_modes"), list) or not agent.get("failure_modes"):
                    validation_errors.append(f"Agent '{agent.get('id')}' must include non-empty failure_modes[]")
                if not isinstance(agent.get("safeguards"), list) or not agent.get("safeguards"):
                    validation_errors.append(f"Agent '{agent.get('id')}' must include non-empty safeguards[]")
                if not isinstance(agent.get("degrades_to"), str) or not agent.get("degrades_to"):
                    validation_errors.append(f"Agent '{agent.get('id')}' missing degrades_to")
                mem_owned = agent.get("memory_owned")
                if isinstance(mem_owned, list):
                    for mo in mem_owned[:12]:
                        if not isinstance(mo, dict):
                            validation_errors.append(f"Agent '{agent.get('id')}' memory_owned entries must be objects")
                            break
                        if mo.get("type") not in {"short_term", "long_term", "episodic", "semantic"}:
                            validation_errors.append(
                                f"Agent '{agent.get('id')}' memory_owned.type must be short_term|long_term|episodic|semantic"
                            )
                            break
                        if not mo.get("purpose") or not mo.get("implementation"):
                            validation_errors.append(
                                f"Agent '{agent.get('id')}' memory_owned entries must include purpose and implementation"
                            )
                            break
            for agent in agents:
                if not isinstance(agent, dict):
                    continue
                raw_subagents = agent.get("subagents")
                if raw_subagents is None:
                    agent["subagents"] = []
                    continue
                if isinstance(raw_subagents, list):
                    normalized: list[str] = []
                    for entry in raw_subagents:
                        if isinstance(entry, str) and entry.strip():
                            normalized.append(entry.strip())
                        elif isinstance(entry, dict):
                            cid = (entry.get("id") or entry.get("name") or "").strip()
                            if cid:
                                normalized.append(cid)
                    agent["subagents"] = normalized[:10]
                else:
                    agent["subagents"] = []
            agent_ids = {a.get("id") for a in agents if isinstance(a, dict) and a.get("id")}
            tool_ids = {t.get("id") for t in tools if isinstance(t, dict) and t.get("id")}
            valid_ids = agent_ids | tool_ids
            if not isinstance(interactions, list) or not interactions:
                validation_errors.append("Architecture must include a non-empty interactions[] list (explicit edges)")
            else:
                bad_edges = 0
                for e in interactions[:120]:
                    if not isinstance(e, dict):
                        bad_edges += 1
                        continue
                    src = e.get("source")
                    tgt = e.get("target")
                    if not isinstance(src, str) or not isinstance(tgt, str):
                        bad_edges += 1
                        continue
                    if src not in valid_ids or tgt not in valid_ids:
                        bad_edges += 1
                if bad_edges:
                    validation_errors.append(f"interactions[] has {bad_edges} invalid edge(s) (bad/missing endpoints)")
            
            if validation_errors and attempt < max_retries:
                notes.append(f"Attempt {attempt + 1} validation failed: {validation_errors}")
                # Add stronger instruction for retry
                prompt += f"\n\nPREVIOUS ATTEMPT FAILED VALIDATION:\n" + "\n".join(validation_errors) + "\n\nFix these issues in your response."
                continue
            elif validation_errors:
                notes.append(f"Validation warnings (final attempt): {validation_errors}")
                break
            notes.append(f"Generated architecture with {len(agents)} agents and {len(architecture.get('tools', []))} tools")
            break
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse architecture JSON (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                notes.append(f"JSON parse error on attempt {attempt + 1}, retrying")
                prompt += "\n\nIMPORTANT: Your previous response was not valid JSON. Return ONLY a valid JSON object."
                continue
            notes.append(f"JSON parse error after {max_retries + 1} attempts")
            architecture = _build_fallback_architecture(goal, selected_patterns)
            notes.append("Using fallback architecture due to parse errors")
            break
        except Exception as e:
            logger.warning(f"LLM call failed in architecture_generator_node: {e}")
            notes.append(f"LLM error: {str(e)[:100]}")
            architecture = _build_fallback_architecture(goal, selected_patterns)
            notes.append("Using fallback architecture due to LLM error")
            break
    else:
        # Loop exhausted without break (shouldn't normally happen but keep defensive fallback)
        if not architecture:
            architecture = _build_fallback_architecture(goal, selected_patterns)
            notes.append("Fallback architecture generated after retries exhausted")
    
    result = {
        "status": "completed" if architecture.get("agents") else "skipped",
        "architecture": architecture,
        "notes": notes,
        "what": f"Generated architecture with {len(architecture.get('agents', []) if isinstance(architecture, dict) else [])} agent(s)",
        "why": (
            f"Used selected patterns: {', '.join([p.get('name','') for p in selected_patterns[:3] if isinstance(p, dict) and p.get('name')])}"
            if selected_patterns
            else "No patterns were selected; generated architecture using best judgment"
        ),
        "alternatives_considered": None,
    }
    existing_design_state = state.get("design_state") or {}
    existing_design_state["architecture"] = result
    
    return {
        "design_state": existing_design_state,
        "architecture_output": architecture,
    }


def _build_fallback_architecture(goal: str, selected_patterns: list) -> dict:
    goal_words = [w.capitalize() for w in goal.split()[:3] if len(w) > 3]
    prefix = goal_words[0] if goal_words else "Task"

    coordinator_id = f"{prefix.lower()}_coordinator"
    worker_id = f"{prefix.lower()}_worker"
    
    return {
        "architecture_class": "supervisor_worker",
        "architecture_class_reason": "",
        "tradeoffs": [
            {
                "decision": "Use a simple supervisor/worker split",
                "alternatives": ["Single agent", "Planner/Executor/Evaluator loop"],
                "why": "Fallback needs a minimal multi-agent structure that still provides separation of concerns.",
            }
        ],
        "overview": f"Architecture for: {goal[:200]}",
        "agents": [
            {
                "id": coordinator_id,
                "name": f"{prefix}Coordinator",
                "responsibility": "Coordinate the overall workflow and delegate tasks",
                "tools": ["task_queue", "status_tracker"],
                "subagents": [worker_id],
                "inputs": ["User request", "Worker progress/results"],
                "outputs": ["Task plan", "Delegated work items", "Final response"],
                "memory_owned": [
                    {
                        "type": "short_term",
                        "purpose": "Track current run state and pending tasks",
                        "implementation": "In-memory state (or Redis for production)",
                    }
                ],
                "failure_modes": ["Invalid or incomplete delegation", "Losing track of task state"],
                "safeguards": ["Use structured task format", "Persist run state periodically"],
                "degrades_to": "Single-agent execution with reduced parallelism",
            },
            {
                "id": worker_id,
                "name": f"{prefix}Processor",
                "responsibility": "Execute the main processing tasks",
                "tools": ["data_handler", "output_generator"],
                "subagents": [],
                "inputs": ["Delegated task", "Relevant context/artifacts"],
                "outputs": ["Intermediate results", "Status updates"],
                "memory_owned": [
                    {
                        "type": "episodic",
                        "purpose": "Record task attempts and outcomes for the current run",
                        "implementation": "Append-only log (or Postgres table in production)",
                    }
                ],
                "failure_modes": ["Tool call failure", "Timeouts under load"],
                "safeguards": ["Retry with backoff", "Validate outputs before returning"],
                "degrades_to": "Return partial results with explicit gaps",
            },
        ],
        "tools": [
            {
                "id": "task_queue",
                "name": "Task Queue",
                "type": "other",
                "io_schema": "{task} -> {queued_task}",
                "failure_handling": "Retry with exponential backoff",
            },
            {
                "id": "status_tracker",
                "name": "Status Tracker",
                "type": "other",
                "io_schema": "{status_update} -> {ack}",
                "failure_handling": "Best-effort; retry on transient errors",
            },
            {
                "id": "data_handler",
                "name": "Data Handler",
                "type": "other",
                "io_schema": "{input} -> {processed}",
                "failure_handling": "Validate input; return structured error on failure",
            },
            {
                "id": "output_generator",
                "name": "Output Generator",
                "type": "other",
                "io_schema": "{processed} -> {output}",
                "failure_handling": "Retry; fall back to simplified output if needed",
            },
        ],
        "interactions": [
            {"source": coordinator_id, "target": worker_id, "kind": "delegates", "label": "Delegate work"},
            {"source": worker_id, "target": coordinator_id, "kind": "returns", "label": "Return results"},
            {"source": coordinator_id, "target": "task_queue", "kind": "tool_call", "label": "Enqueue tasks"},
            {"source": coordinator_id, "target": "status_tracker", "kind": "tool_call", "label": "Track progress"},
            {"source": worker_id, "target": "data_handler", "kind": "tool_call", "label": "Process inputs"},
            {"source": worker_id, "target": "output_generator", "kind": "tool_call", "label": "Generate output"},
        ],
        "memory": {
            "short_term": {"purpose": "Track current task state", "implementation": "In-memory dict"},
            "long_term": {"purpose": "Store completed results", "implementation": "Database"},
        },
        "control_loop": {
            "flow": f"START -> {prefix}Coordinator -> {prefix}Processor -> END",
            "termination_conditions": ["All tasks completed", "Max iterations reached"],
        },
        "bounded_autonomy": {
            "constraints": [{"constraint": "Max steps", "value": "20", "action_on_breach": "Terminate"}],
            "permission_gates": [],
            "human_in_loop": [],
        },
        "implementation_notes": ["This is a fallback architecture - customize based on specific requirements"],
        "start_simple_recommendation": "Start with a single agent and add complexity as needed",
    }


def output_formatter_node(state: State) -> Dict[str, Any]:
    design_state = state.get("design_state") or {}
    goal = _coerce_str(state.get("goal"), max_len=300) or "System"
    
    # Get architecture from design_state
    architecture_data = design_state.get("architecture") or {}
    architecture = architecture_data.get("architecture") or state.get("architecture_output") or {}
    
    notes: list[str] = []
    
    # Extract architecture components
    overview = architecture.get("overview", "Architecture design for the specified goal.")
    agents = architecture.get("agents", [])
    tools = architecture.get("tools", [])
    memory = architecture.get("memory", {})
    control_loop = architecture.get("control_loop", {})
    bounded_autonomy = architecture.get("bounded_autonomy", {})
    implementation_notes = architecture.get("implementation_notes", [])
    start_simple = architecture.get("start_simple_recommendation", "")
    
    # Build markdown output
    output_parts = []
    
    # Title and Overview
    output_parts.append(f"# Architecture Design: {goal}\n")
    output_parts.append(f"## Overview\n{overview}\n")
    
    # Agents Table
    output_parts.append("## Agents\n")
    if agents:
        output_parts.append("| Agent | Responsibility | Tools |")
        output_parts.append("|-------|----------------|-------|")
        for agent in agents:
            name = agent.get("name", "Unknown")
            responsibility = agent.get("responsibility", "")[:100]
            agent_tools = ", ".join(agent.get("tools", [])[:3]) or "None"
            output_parts.append(f"| **{name}** | {responsibility} | {agent_tools} |")
        output_parts.append("")
    else:
        output_parts.append("*No agents defined in architecture.*\n")
    
    # Tools Table
    output_parts.append("## Tools\n")
    if tools:
        output_parts.append("| Tool | Type | I/O Schema | Failure Handling |")
        output_parts.append("|------|------|------------|------------------|")
        for tool in tools:
            name = tool.get("name", "Unknown")
            tool_type = tool.get("type", "other")
            io_schema = tool.get("io_schema", "")[:50]
            failure = tool.get("failure_handling", "")[:40]
            output_parts.append(f"| **{name}** | {tool_type} | {io_schema} | {failure} |")
        output_parts.append("")
    else:
        output_parts.append("*No tools defined in architecture.*\n")
    
    # Memory Architecture
    output_parts.append("## Memory Architecture\n")
    if memory:
        for mem_type, mem_config in memory.items():
            if isinstance(mem_config, dict):
                purpose = mem_config.get("purpose", "")
                impl = mem_config.get("implementation", "")
                output_parts.append(f"### {mem_type.replace('_', ' ').title()}")
                output_parts.append(f"- **Purpose:** {purpose}")
                output_parts.append(f"- **Implementation:** {impl}\n")
    else:
        output_parts.append("*No memory architecture defined.*\n")
    
    # Control Loop
    output_parts.append("## Control Loop\n")
    if control_loop:
        flow = control_loop.get("flow", "Not specified")
        termination = control_loop.get("termination_conditions", [])
        output_parts.append(f"**Flow:** `{flow}`\n")
        if termination:
            output_parts.append("**Termination Conditions:**")
            for cond in termination:
                output_parts.append(f"- {cond}")
        output_parts.append("")
    else:
        output_parts.append("*No control loop defined.*\n")
    
    # Bounded Autonomy (Safety)
    output_parts.append("## Safety & Bounded Autonomy\n")
    if bounded_autonomy:
        constraints = bounded_autonomy.get("constraints", [])
        permission_gates = bounded_autonomy.get("permission_gates", [])
        human_in_loop = bounded_autonomy.get("human_in_loop", [])
        
        if constraints:
            output_parts.append("### Constraints")
            output_parts.append("| Constraint | Value | Action on Breach |")
            output_parts.append("|------------|-------|------------------|")
            for c in constraints:
                if isinstance(c, dict):
                    output_parts.append(f"| {c.get('constraint', '')} | {c.get('value', '')} | {c.get('action_on_breach', '')} |")
            output_parts.append("")
        
        if permission_gates:
            output_parts.append("### Permission Gates (Require Approval)")
            for gate in permission_gates:
                output_parts.append(f"- {gate}")
            output_parts.append("")
        
        if human_in_loop:
            output_parts.append("### Human-in-the-Loop Scenarios")
            for scenario in human_in_loop:
                output_parts.append(f"- {scenario}")
            output_parts.append("")
    else:
        output_parts.append("*No safety constraints defined.*\n")
    
    # Implementation Notes
    output_parts.append("## Implementation Notes\n")
    if implementation_notes:
        for note in implementation_notes:
            output_parts.append(f"- {note}")
        output_parts.append("")
    else:
        output_parts.append("*No implementation notes provided.*\n")
    
    # Start Simple Recommendation
    if start_simple:
        output_parts.append("## Getting Started\n")
        output_parts.append(f"> **Recommendation:** {start_simple}\n")
    
    # Combine all parts
    output = "\n".join(output_parts)
    notes.append(f"Formatted output with {len(agents)} agents, {len(tools)} tools")
    
    result = {
        "status": "completed",
        "formatted_output": output,
        "notes": notes,
    }
    
    # Store result in design_state.output for design_agent to aggregate
    existing_design_state = state.get("design_state") or {}
    existing_design_state["output"] = result
    
    return {
        "design_state": existing_design_state,
        "output": output,
    }


def design_agent(state: State) -> Dict[str, any]:
    plan_state = state.get("plan_state") or {}
    existing = state.get("design_state")
    design_state = _initial_design_state(existing)

    # Get results from subnodes (they update state directly via graph edges)
    architecture_result = design_state.get("architecture", {})
    output_result = design_state.get("output", {})
    
    # Check status of subnodes
    architecture_status = architecture_result.get("status", "").lower() if isinstance(architecture_result, dict) else ""
    output_status = output_result.get("status", "").lower() if isinstance(output_result, dict) else ""
    
    architecture_completed = architecture_status == "completed" or architecture_status == "skipped"
    output_completed = output_status == "completed" or output_status == "skipped"
    
    # If subnodes are not all complete, routing will handle it
    # This function only aggregates when all are done
    if not (architecture_completed and output_completed):
        # Still update design_state with what we have
        if architecture_completed:
            design_state["architecture"] = architecture_result
        if output_completed:
            design_state["output"] = output_result
        
        # Return minimal updates - routing will handle next step
        return {
            "design_state": design_state,
        }
    
    # All subnodes are complete - aggregate results
    design_state["architecture"] = architecture_result
    design_state["output"] = output_result
    
    # Aggregate notes
    for result in [architecture_result, output_result]:
        if isinstance(result, dict):
            notes = result.get("notes")
            if isinstance(notes, list):
                for note in notes:
                    design_state["notes"] = _append_design_note(design_state.get("notes", []), note)
            elif notes:
                design_state["notes"] = _append_design_note(design_state.get("notes", []), notes)
    
    # Determine overall status
    statuses = [architecture_status, output_status]
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
    
    # Get agent roles for context
    components_data = design_state.get("components", {})
    agent_roles = components_data.get("agent_roles") or []
    agent_summary = "\n".join(
        f"- {_coerce_str(r.get('name'), max_len=40)}: {_coerce_str(r.get('responsibility'), max_len=60)}"
        for r in agent_roles if isinstance(r, dict)
    )

    schema_desc = json.dumps(
        {
            "status": "completed",
            "notes": ["risk description"],
            "bounded_autonomy": {
                "constraints": [
                    {"constraint": "Max steps", "value": "20", "action_on_breach": "Terminate and return partial result"},
                    {"constraint": "Token budget", "value": "50000", "action_on_breach": "Switch to smaller model"}
                ],
                "permission_gates": ["Action requiring explicit approval before execution"],
                "human_in_loop": ["High-stakes scenario requiring human review"]
            }
        },
        ensure_ascii=False,
    )
    sys = SystemMessage(content=(
        "You assess architecture risks AND define safety constraints for agentic systems.\n\n"
        "Return JSON only matching this schema:\n"
        f"{schema_desc}\n\n"
        "CRITICAL - For bounded_autonomy, define:\n"
        "1. CONSTRAINTS: Step limits, token budgets, time limits, cost caps - with specific values and breach actions\n"
        "2. PERMISSION GATES: Actions that should NEVER run automatically (e.g., sending emails, making payments, deleting data)\n"
        "3. HUMAN-IN-LOOP: Scenarios where human approval is required (high severity, irreversible actions, ambiguous decisions)\n\n"
        "Be SPECIFIC with numerical limits based on the system's complexity and risk profile."
    ))

    prompt_lines = []
    if plan_summary:
        prompt_lines.append(f"Plan summary:\n{plan_summary}")
    if agent_summary:
        prompt_lines.append(f"\nAgent roles:\n{agent_summary}")
    if comp_summary:
        prompt_lines.append(f"\nComponents:\n{comp_summary}")
    prompt = "\n".join(prompt_lines) if prompt_lines else "No plan/components provided."

    run_id = state.get("metadata", {}).get("run_id")
    raw = call_brain([sys, HumanMessage(content=prompt)], state=state, run_id=run_id, node="risk_node")
    parsed = json_only(raw) or {}
    notes = _coerce_str_list(parsed.get("notes"), max_items=8, max_len=200)
    status = _coerce_str(parsed.get("status"), max_len=16) or ("completed" if notes else "skipped")
    
    # Extract bounded autonomy constraints
    bounded_autonomy = parsed.get("bounded_autonomy") or {}

    result = {
        "status": status,
        "notes": notes,
        "bounded_autonomy": bounded_autonomy,
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


@lru_cache(maxsize=1)
def _load_tool_catalog() -> dict[str, Any]:
    """Load the tool catalog v1 from JSON file."""
    catalog_path = os.path.join(os.path.dirname(__file__), "tool_catalog_v1.json")
    try:
        with open(catalog_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load tool_catalog_v1.json: {e}")
        return {"version": "v1", "tools": [], "categories": []}


def _map_tool_to_catalog(tool_name: str, tool_type: str, catalog: dict) -> Optional[str]:
    """Map a legacy tool name to a catalog tool ID."""
    catalog_tools = catalog.get("tools", [])
    tool_name_lower = tool_name.lower()
    tool_type_lower = tool_type.lower() if tool_type else ""
    
    # Direct ID match
    for ct in catalog_tools:
        if ct.get("id", "").lower() == tool_name_lower:
            return ct["id"]
    
    # Name match
    for ct in catalog_tools:
        if ct.get("display_name", "").lower() == tool_name_lower:
            return ct["id"]
    
    # Category-based mapping
    category_map = {
        "db": "db_storage",
        "database": "db_storage",
        "api": "deployment_hosting",
        "llm": "orchestration",
        "search": "vector_store",
        "queue": "queue_workflow",
        "auth": "auth_identity",
    }
    
    mapped_category = category_map.get(tool_type_lower)
    if mapped_category:
        for ct in catalog_tools:
            if ct.get("category") == mapped_category:
                return ct["id"]
    
    # Keyword-based mapping
    keyword_map = {
        "postgres": "postgres_supabase",
        "supabase": "postgres_supabase",
        "redis": "redis_streams",
        "queue": "sqs",
        "vector": "pgvector",
        "embedding": "pgvector",
        "auth": "supabase_auth",
        "login": "supabase_auth",
        "deploy": "vercel",
        "host": "vercel",
        "monitor": "opentelemetry",
        "trace": "langsmith",
        "log": "opentelemetry",
    }
    
    for keyword, tool_id in keyword_map.items():
        if keyword in tool_name_lower:
            return tool_id
    
    return None


def _build_asc_v11(state: State) -> dict[str, Any]:

    goal = _coerce_str(state.get("goal"), max_len=300) or "System"
    generated_at = datetime.now(timezone.utc).isoformat()
    
    # Load tool catalog
    catalog = _load_tool_catalog()
    
    # Pull design artifacts
    design_state = state.get("design_state") if isinstance(state.get("design_state"), dict) else {}
    architecture_artifact = design_state.get("architecture") if isinstance(design_state.get("architecture"), dict) else {}
    architecture = (
        architecture_artifact.get("architecture")
        if isinstance(architecture_artifact.get("architecture"), dict)
        else state.get("architecture_output")
        if isinstance(state.get("architecture_output"), dict)
        else {}
    )
    # Get pattern info
    selected_patterns = state.get("selected_patterns") or []
    pattern_ids = [p.get("id") for p in selected_patterns if isinstance(p, dict) and p.get("id")]
    
    # Plan state for assumptions/missing info
    plan_scope = state.get("plan_scope") if isinstance(state.get("plan_scope"), dict) else {}
    plan_state = state.get("plan_state") if isinstance(state.get("plan_state"), dict) else {}
    research_state = state.get("research_state") if isinstance(state.get("research_state"), dict) else {}

    legacy_agents = architecture.get("agents", [])
    num_agents = len(legacy_agents) if isinstance(legacy_agents, list) else 0
    
    # Determine architecture type from patterns or control loop (legacy field)
    control_loop = architecture.get("control_loop", {})
    arch_type = "react"  # default
    if pattern_ids:
        arch_type = pattern_ids[0]
    elif isinstance(control_loop, dict):
        flow = control_loop.get("flow", "").lower()
        if "supervisor" in flow or "delegate" in flow:
            arch_type = "supervisor"
        elif "plan" in flow and "execute" in flow:
            arch_type = "plan-and-execute"
        elif "reflect" in flow or "critic" in flow:
            arch_type = "reflection"
    
    blocking_issues = _coerce_str_list(plan_scope.get("blocking_issues"), max_items=8, max_len=160)
    info_issues = _coerce_str_list(plan_scope.get("info_issues"), max_items=8, max_len=160)
    
    # Strict architecture class (new field)
    arch_class = architecture.get("architecture_class")
    if arch_class not in {
        "hierarchical_orchestrator",
        "supervisor_worker",
        "planner_executor_evaluator_loop",
        "hybrid",
    }:
        # Defensive mapping for legacy runs / fallbacks
        if arch_type in {"supervisor", "supervisor_worker"}:
            arch_class = "supervisor_worker"
        elif arch_type in {"plan-and-execute", "planner_executor_evaluator_loop"}:
            arch_class = "planner_executor_evaluator_loop"
        else:
            arch_class = "hierarchical_orchestrator"
    arch_class_reason = architecture.get("architecture_class_reason") if arch_class == "hybrid" else None
    tradeoffs = architecture.get("tradeoffs") if isinstance(architecture.get("tradeoffs"), list) else []

    decision = {
        "single_vs_multi": "multi" if num_agents > 1 else "single",
        "architecture_type": arch_type,
        "architecture_type_reason": architecture_artifact.get("why") or f"Selected {arch_type} pattern based on goal requirements",
        "architecture_class": arch_class,
        "architecture_class_reason": arch_class_reason,
        "tradeoffs": tradeoffs,
        "confidence": 0.8 if not blocking_issues else 0.5,
        "assumptions": _coerce_str_list(plan_scope.get("assumptions"), max_items=8, max_len=200),
        "missing_info": blocking_issues + info_issues,
        "pattern_influences": pattern_ids[:3],
        "pattern_deviation_notes": [],
    }

    agents_v11 = []
    legacy_tools = architecture.get("tools", [])
    
    # Precompute reports_to by inverting subagents[] for parent/child clarity
    parent_of: dict[str, str] = {}
    if isinstance(legacy_agents, list):
        for a in legacy_agents:
            if not isinstance(a, dict):
                continue
            pid = a.get("id") or a.get("name", "").lower().replace(" ", "_")
            subs = a.get("subagents", [])
            if not pid or not isinstance(subs, list):
                continue
            for cid in subs[:20]:
                if isinstance(cid, str) and cid.strip() and cid.strip() not in parent_of:
                    parent_of[cid.strip()] = pid

    for agent in legacy_agents:
        if not isinstance(agent, dict):
            continue
        
        agent_id = agent.get("id") or agent.get("name", "").lower().replace(" ", "_")
        
        # Map legacy tools to catalog
        agent_tool_access = []
        for tool_name in agent.get("tools", []):
            catalog_id = _map_tool_to_catalog(str(tool_name), "", catalog)
            if catalog_id:
                agent_tool_access.append({
                    "tool_id": catalog_id,
                    "scopes": [],
                    "usage_notes": f"Used by {agent.get('name', agent_id)}",
                })
        
        # Determine model class based on responsibility
        responsibility = (agent.get("responsibility") or "").lower()
        model_class = "mid"  # default
        if any(kw in responsibility for kw in ["coordinate", "supervise", "orchestrate", "plan"]):
            model_class = "frontier"
        elif any(kw in responsibility for kw in ["simple", "basic", "route", "validate"]):
            model_class = "small"
        
        inputs = agent.get("inputs") if isinstance(agent.get("inputs"), list) else []
        outputs = agent.get("outputs") if isinstance(agent.get("outputs"), list) else []
        mem_owned = agent.get("memory_owned") if isinstance(agent.get("memory_owned"), list) else []
        mem_specs = []
        for mo in mem_owned[:12]:
            if not isinstance(mo, dict):
                continue
            mem_type = mo.get("type")
            if mem_type not in {"short_term", "long_term", "episodic", "semantic"}:
                continue
            purpose = _coerce_str(mo.get("purpose"), max_len=200)
            impl = _coerce_str(mo.get("implementation"), max_len=240)
            if purpose and impl:
                mem_specs.append(
                    {
                        "type": mem_type,
                        "purpose": purpose,
                        "implementation_hint": impl,
                    }
                )

        agent_spec = {
            "id": agent_id,
            "name": agent.get("name") or agent_id,
            "role": agent.get("responsibility") or "Agent role",
            "boundaries": [agent.get("responsibility") or "Primary responsibility"],
            "inputs": _coerce_str_list(inputs, max_items=12, max_len=120),
            "outputs": _coerce_str_list(outputs, max_items=12, max_len=120),
            "reports_to": parent_of.get(agent_id),
            "subagents": agent.get("subagents", []),
            "model_class": model_class,
            "model_class_rationale": f"Selected {model_class} based on {agent.get('responsibility', 'role')}",
            "tools": agent_tool_access,
            "memory": mem_specs,
            "orchestration_constraints": [],
        }
        agents_v11.append(agent_spec)
    
    legacy_interactions = architecture.get("interactions", [])
    
    agent_ids_v11 = {a.get("id") for a in agents_v11 if isinstance(a, dict) and a.get("id")}

    # Build nodes
    graph_nodes = [{"id": "start", "type": "start", "label": "Start"}]
    for agent in agents_v11:
        graph_nodes.append({
            "id": agent["id"],
            "type": "agent",
            "label": agent["name"],
            "agent_id": agent["id"],
        })
    graph_nodes.append({"id": "end", "type": "end", "label": "End"})
    
    # Build edges from legacy interactions (agents-only)
    graph_edges = []
    for interaction in legacy_interactions:
        if not isinstance(interaction, dict):
            continue
        
        source = interaction.get("source")
        target = interaction.get("target")
        kind = interaction.get("kind", "control").lower()

        # Agents-only: ignore tool endpoints
        if source not in agent_ids_v11 and source not in {"start", "end"}:
            continue
        if target not in agent_ids_v11 and target not in {"start", "end"}:
            continue
        if source in {"start", "end"} and target in {"start", "end"}:
            continue
        
        edge_type = "data" if kind in ["reads", "writes", "returns"] else "control"
        
        graph_edges.append({
            "source": source,
            "target": target,
            "edge_type": edge_type,
            "label": interaction.get("label") or kind,
            "condition": None,
        })

    # Ensure supervisor/worker relationships are explicit in the graph (control + return paths)
    existing_pairs = {(e.get("source"), e.get("target"), e.get("edge_type")) for e in graph_edges if isinstance(e, dict)}
    for a in agents_v11:
        if not isinstance(a, dict):
            continue
        parent_id = a.get("id")
        subs = a.get("subagents", [])
        if not parent_id or not isinstance(subs, list):
            continue
        for child_id in subs[:20]:
            if child_id not in agent_ids_v11:
                continue
            if (parent_id, child_id, "control") not in existing_pairs:
                graph_edges.append(
                    {
                        "source": parent_id,
                        "target": child_id,
                        "edge_type": "control",
                        "label": "supervises",
                        "condition": None,
                    }
                )
                existing_pairs.add((parent_id, child_id, "control"))
            if (child_id, parent_id, "data") not in existing_pairs:
                graph_edges.append(
                    {
                        "source": child_id,
                        "target": parent_id,
                        "edge_type": "data",
                        "label": "reports",
                        "condition": None,
                    }
                )
                existing_pairs.add((child_id, parent_id, "data"))
    
    # Add start/end edges if not present
    if agents_v11 and not any(e.get("source") == "start" for e in graph_edges):
        graph_edges.insert(0, {
            "source": "start",
            "target": agents_v11[0]["id"],
            "edge_type": "control",
            "label": "Begin",
        })
    if agents_v11 and not any(e.get("target") == "end" for e in graph_edges):
        graph_edges.append({
            "source": agents_v11[-1]["id"],
            "target": "end",
            "edge_type": "control",
            "label": "Complete",
        })
    
    # Build loops from control edges (best-effort)
    loops = []
    termination_conditions = []
    if isinstance(control_loop, dict):
        termination_conditions = _coerce_str_list(control_loop.get("termination_conditions"), max_items=5, max_len=200)
    
    graph = {
        "nodes": graph_nodes,
        "edges": graph_edges,
        "loops": loops,
        "entry_point": "start",
        "exit_points": ["end"],
        "termination_conditions": termination_conditions,
    }

    # Derive execution order from CONTROL edges (agents-only); tolerate cycles by falling back.
    control_edges = [
        e
        for e in graph_edges
        if isinstance(e, dict)
        and e.get("edge_type") == "control"
        and e.get("target") in agent_ids_v11
        and e.get("source") in (agent_ids_v11 | {"start"})
    ]
    indeg: dict[str, int] = {aid: 0 for aid in agent_ids_v11}
    succ: dict[str, list[str]] = {aid: [] for aid in agent_ids_v11}
    preds: dict[str, list[str]] = {aid: [] for aid in agent_ids_v11}
    for e in control_edges:
        s = e.get("source")
        t = e.get("target")
        if s == "start":
            indeg[t] = indeg.get(t, 0) + 0
            continue
        if s in agent_ids_v11 and t in agent_ids_v11:
            succ.setdefault(s, []).append(t)
            preds.setdefault(t, []).append(s)
            indeg[t] = indeg.get(t, 0) + 1

    # Kahn's algorithm
    q = [aid for aid, d in indeg.items() if d == 0]
    topo: list[str] = []
    while q:
        n = q.pop(0)
        topo.append(n)
        for m in succ.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                q.append(m)

    has_cycle = len(topo) != len(agent_ids_v11)
    ordered_agents = topo if topo else [a["id"] for a in agents_v11]
    if has_cycle:
        ordered_agents = [a["id"] for a in agents_v11]
        if ordered_agents:
            loops.append(
                {
                    "id": "loop-1",
                    "name": "Agent loop",
                    "entry_node": ordered_agents[0],
                    "exit_node": ordered_agents[-1],
                    "max_iterations": None,
                    "termination_conditions": termination_conditions,
                }
            )

    execution_steps = []
    for idx, aid in enumerate(ordered_agents):
        agent_obj = next((a for a in agents_v11 if a.get("id") == aid), None) or {}
        inbound = preds.get(aid, [])
        outbound = succ.get(aid, [])
        step = {
            "order": idx + 1,
            "agent_id": aid,
            "action": agent_obj.get("role") or "Execute step",
            "inputs_from": inbound or (["user"] if idx == 0 else []),
            "outputs_to": outbound or (["user"] if idx == len(ordered_agents) - 1 else []),
            "can_loop": bool(has_cycle),
            "human_checkpoint": False,
        }
        execution_steps.append(step)
    
    execution_flow = {
        "steps": execution_steps,
        "parallel_groups": [],
        "critical_path": list(range(1, len(execution_steps) + 1)),
    }
 
    selected_tools = []
    used_tool_ids = set()
    
    for tool in legacy_tools:
        if not isinstance(tool, dict):
            continue
        
        tool_name = tool.get("name") or tool.get("id") or ""
        tool_type = tool.get("type") or ""
        
        catalog_id = _map_tool_to_catalog(tool_name, tool_type, catalog)
        if not catalog_id or catalog_id in used_tool_ids:
            continue
        
        used_tool_ids.add(catalog_id)
        
        # Find catalog entry for details
        catalog_entry = next((ct for ct in catalog.get("tools", []) if ct.get("id") == catalog_id), {})
        
        # Find alternatives from catalog
        alternatives = []
        for alt_id in catalog_entry.get("alternatives", [])[:2]:
            alt_entry = next((ct for ct in catalog.get("tools", []) if ct.get("id") == alt_id), None)
            if alt_entry:
                alternatives.append({
                    "tool_id": alt_id,
                    "reason": f"Alternative in {catalog_entry.get('category', 'same')} category",
                })
        
        # Build agent permissions
        agent_permissions = {}
        for agent in agents_v11:
            for ta in agent.get("tools", []):
                if ta.get("tool_id") == catalog_id:
                    agent_permissions[agent["id"]] = ta.get("scopes", [])
        
        selected_tools.append({
            "id": catalog_id,
            "display_name": catalog_entry.get("display_name") or tool_name,
            "category": catalog_entry.get("category") or "other",
            "default_choice_reason": tool.get("failure_handling") or "Selected based on architecture requirements",
            "alternatives": alternatives,
            "auth_config": catalog_entry.get("auth"),
            "failure_handling": tool.get("failure_handling") or "Retry with backoff",
            "agent_permissions": agent_permissions,
        })
    
    tooling = {
        "tool_catalog_version": "v1",
        "tools": selected_tools,
    }
    

    # Map per-agent deployability constraints from architecture JSON (source of truth)
    legacy_agent_by_id = {}
    for la in legacy_agents if isinstance(legacy_agents, list) else []:
        if isinstance(la, dict):
            lid = la.get("id") or la.get("name", "").lower().replace(" ", "_")
            if lid:
                legacy_agent_by_id[lid] = la

    deployability_constraints = []
    for agent in agents_v11:
        la = legacy_agent_by_id.get(agent.get("id") or "")
        failure_modes = la.get("failure_modes") if isinstance(la, dict) and isinstance(la.get("failure_modes"), list) else ["timeout", "rate_limit"]
        safeguards = la.get("safeguards") if isinstance(la, dict) and isinstance(la.get("safeguards"), list) else ["Retry with exponential backoff"]
        degrades_to = la.get("degrades_to") if isinstance(la, dict) and isinstance(la.get("degrades_to"), str) else "Return partial results with explicit gaps"
        constraint = {
            "agent_id": agent["id"],
            "model_class": agent.get("model_class", "mid"),
            "estimated_latency_ms": 2000 if agent.get("model_class") == "frontier" else 500,
            "estimated_cost_per_call": "$0.05" if agent.get("model_class") == "frontier" else "$0.01",
            "scaling_notes": "Horizontal scaling via multiple instances",
            "failure_modes": _coerce_str_list(failure_modes, max_items=8, max_len=140),
            "safeguards": _coerce_str_list(safeguards, max_items=8, max_len=140),
            "degrades_to": _coerce_str(degrades_to, max_len=180) or "Return partial results with explicit gaps",
            "recovery_strategy": "Retry with exponential backoff",
        }
        deployability_constraints.append(constraint)
    
    deployability = {
        "constraints": deployability_constraints,
        "orchestration_platform": "langgraph",
        "orchestration_platform_reason": "Selected LangGraph for stateful agent orchestration with persistence",
        "infrastructure_notes": [
            "Deploy on serverless infrastructure for cost efficiency",
            "Use Redis for short-term state, PostgreSQL for long-term",
        ],
    }
    

    missing_for_ready = decision.get("missing_info", [])
    assumptions_made = decision.get("assumptions", [])
    
    product_state = {
        "status": "ready_to_build" if not missing_for_ready and len(assumptions_made) <= 3 else "draft",
        "missing_for_ready": missing_for_ready,
        "assumptions_made": assumptions_made,
        "confidence_score": decision.get("confidence", 0.7),
    }
    
    plan_summary = _coerce_str(state.get("plan"), max_len=1_200) or _coerce_str(plan_state.get("summary"), max_len=1_200)
    overview = _coerce_str(architecture.get("overview"), max_len=600)
    kickoff_summary = plan_summary or overview or f"Architecture starter kit for: {goal}"
    
    plan_risks = _coerce_str_list(plan_scope.get("risks"), max_items=8, max_len=160)
    research_risks = _coerce_str_list(research_state.get("risks"), max_items=8, max_len=160)
    critic_state = state.get("critic_state") if isinstance(state.get("critic_state"), dict) else {}
    critic_notes = _coerce_str_list(critic_state.get("notes"), max_items=8, max_len=160)
    risks = _limit_strings([*plan_risks, *research_risks, *critic_notes], limit=10)
    
    research_highlights = _coerce_str_list(research_state.get("highlights"), max_items=7, max_len=260)
    citations_raw = research_state.get("citations")
    citations = []
    if isinstance(citations_raw, list):
        for c in citations_raw[:12]:
            if not isinstance(c, dict):
                continue
            url = _coerce_str(c.get("url"), max_len=320)
            title = _coerce_str(c.get("title"), max_len=180)
            source = _coerce_str(c.get("source"), max_len=60)
            item = {k: v for k, v in {"source": source, "url": url, "title": title}.items() if v is not None}
            if item:
                citations.append(item)
    citations = _limit_dicts(citations, limit=7)
    
    # Build ASC v1.1
    contract = _strip_nulls({
        "version": "v1.1",
        "generated_at": generated_at,
        "goal": goal,
        "product_state": product_state,
        "decision": decision,
        "agents": agents_v11,
        "graph": graph,
        "execution_flow": execution_flow,
        "tooling": tooling,
        "deployability": deployability,
        "kickoff": {
            "summary": kickoff_summary,
            "open_questions": blocking_issues + info_issues,
            "risks": risks,
        },
        "research": {
            "highlights": research_highlights,
            "citations": citations,
            "risks": _coerce_str_list(research_state.get("risks"), max_items=8, max_len=160),
        },
        "quality": {
            "critic": {
                "notes": critic_notes,
            },
        },
        "build": {
            "milestones": _coerce_str_list(plan_state.get("intermediate_milestones"), max_items=10, max_len=180),
            "steps": [],
            "first_tasks": [],
        },
    })
    
    return contract


def _build_asc_v1(state: State) -> dict[str, Any]:
    goal = _coerce_str(state.get("goal"), max_len=300) or "System"
    generated_at = datetime.now(timezone.utc).isoformat()

    # Pull design artifacts (Design phase)
    design_state = state.get("design_state") if isinstance(state.get("design_state"), dict) else {}
    architecture_artifact = (
        design_state.get("architecture") if isinstance(design_state.get("architecture"), dict) else {}
    )
    architecture = (
        architecture_artifact.get("architecture")
        if isinstance(architecture_artifact.get("architecture"), dict)
        else state.get("architecture_output")
        if isinstance(state.get("architecture_output"), dict)
        else {}
    )
    output_artifact = design_state.get("output") if isinstance(design_state.get("output"), dict) else {}

    # Top-level planner/research/critic/evals artifacts
    plan_scope = state.get("plan_scope") if isinstance(state.get("plan_scope"), dict) else {}
    plan_state = state.get("plan_state") if isinstance(state.get("plan_state"), dict) else {}
    research_state = state.get("research_state") if isinstance(state.get("research_state"), dict) else {}
    critic_state = state.get("critic_state") if isinstance(state.get("critic_state"), dict) else {}
    eval_state = state.get("eval_state") if isinstance(state.get("eval_state"), dict) else {}

    # Output text (prefer final output)
    output_text = _coerce_str(state.get("output"), max_len=6_000)
    if not output_text:
        formatted = output_artifact.get("formatted_output") if isinstance(output_artifact.get("formatted_output"), str) else None
    plan_summary = _coerce_str(state.get("plan"), max_len=1_200) or _coerce_str(plan_state.get("summary"), max_len=1_200)
    overview = _coerce_str(architecture.get("overview"), max_len=600)
    kickoff_summary = plan_summary or overview or f"Architecture starter kit for: {goal}"

    blocking_issues = _coerce_str_list(plan_scope.get("blocking_issues"), max_items=8, max_len=160)
    info_issues = _coerce_str_list(plan_scope.get("info_issues"), max_items=8, max_len=160)
    plan_risks = _coerce_str_list(plan_scope.get("risks"), max_items=8, max_len=160)
    plan_risks = plan_risks or _coerce_str_list(plan_state.get("risks"), max_items=8, max_len=160)
    research_risks = _coerce_str_list(research_state.get("risks"), max_items=8, max_len=160)
    critic_notes = _coerce_str_list(critic_state.get("notes"), max_items=8, max_len=160)

    risks = _limit_strings([*plan_risks, *research_risks, *critic_notes], limit=10)
    open_questions = _limit_strings([*blocking_issues, *info_issues], limit=10)

    # Research (trim aggressively)
    research_highlights = _coerce_str_list(research_state.get("highlights"), max_items=7, max_len=260)
    citations_raw = research_state.get("citations")
    citations: list[dict[str, Any]] = []
    if isinstance(citations_raw, list):
        for c in citations_raw[:12]:
            if not isinstance(c, dict):
                continue
            url = _coerce_str(c.get("url"), max_len=320)
            title = _coerce_str(c.get("title"), max_len=180)
            source = _coerce_str(c.get("source"), max_len=60)
            item = {k: v for k, v in {"source": source, "url": url, "title": title}.items() if v is not None}
            if item:
                citations.append(item)
    citations = _limit_dicts(citations, limit=7)

    # Build plan (trim to first 12 steps)
    milestones = plan_state.get("intermediate_milestones")
    milestones_out = _coerce_str_list(milestones, max_items=10, max_len=180)

    steps_out: list[dict[str, Any]] = []
    steps_raw = plan_state.get("steps")
    if isinstance(steps_raw, list):
        for idx, step in enumerate(steps_raw[:12]):
            if not isinstance(step, dict):
                continue
            sid = _coerce_str(step.get("id"), max_len=80) or f"step-{idx+1}"
            title = _coerce_str(step.get("title"), max_len=140) or sid
            detail = _coerce_str(step.get("detail"), max_len=400)
            steps_out.append(_strip_nulls({"id": sid, "title": title, "detail": detail}))

    atomic_tasks_out: list[dict[str, Any]] = []
    atomic_raw = plan_state.get("atomic_tasks")
    if isinstance(atomic_raw, list):
        for idx, task in enumerate(atomic_raw[:12]):
            if not isinstance(task, dict):
                continue
            tid = _coerce_str(task.get("id"), max_len=80) or f"task-{idx+1}"
            title = _coerce_str(task.get("title"), max_len=140) or tid
            detail = _coerce_str(task.get("detail"), max_len=400)
            atomic_tasks_out.append(_strip_nulls({"id": tid, "title": title, "detail": detail}))

    # Telemetry (optional)
    telemetry_artifact = eval_state.get("telemetry") if isinstance(eval_state.get("telemetry"), dict) else {}
    telemetry = telemetry_artifact.get("telemetry") if isinstance(telemetry_artifact.get("telemetry"), dict) else {}
    telemetry_notes = _coerce_str_list(telemetry_artifact.get("notes"), max_items=6, max_len=200)

    # Architecture block (runtime-neutral; diagram removed)
    arch_block = _strip_nulls(
        {
            "overview": overview,
            "agents": architecture.get("agents") if isinstance(architecture.get("agents"), list) else [],
            "tools": architecture.get("tools") if isinstance(architecture.get("tools"), list) else [],
            "interactions": architecture.get("interactions") if isinstance(architecture.get("interactions"), list) else [],
            "memory": architecture.get("memory") if isinstance(architecture.get("memory"), dict) else {},
            "control_loop": architecture.get("control_loop") if isinstance(architecture.get("control_loop"), dict) else {},
            "bounded_autonomy": architecture.get("bounded_autonomy") if isinstance(architecture.get("bounded_autonomy"), dict) else {},
            "output": output_text,
        }
    )

    contract = _strip_nulls(
        {
            "version": "v1",
            "generated_at": generated_at,
            "goal": goal,
            "kickoff": {
                "summary": kickoff_summary,
                "open_questions": open_questions,
                "risks": risks,
            },
            "architecture": arch_block,
            "research": {
                "highlights": research_highlights,
                "citations": citations,
                "risks": _coerce_str_list(research_state.get("risks"), max_items=8, max_len=160),
            },
            "quality": {
                "critic": {
                    "notes": critic_notes,
                    "review_status": _coerce_str((critic_state.get("review") or {}).get("status"), max_len=16)
                    if isinstance(critic_state.get("review"), dict)
                    else None,
                    "hallucination_status": _coerce_str((critic_state.get("hallucination") or {}).get("status"), max_len=16)
                    if isinstance(critic_state.get("hallucination"), dict)
                    else None,
                    "risk_status": _coerce_str((critic_state.get("risk") or {}).get("status"), max_len=16)
                    if isinstance(critic_state.get("risk"), dict)
                    else None,
                },
                "telemetry": {
                    "telemetry": telemetry,
                    "notes": telemetry_notes,
                    "status": _coerce_str(telemetry_artifact.get("status"), max_len=16),
                },
            },
            "build": {
                "milestones": milestones_out,
                "steps": steps_out,
                "first_tasks": atomic_tasks_out,
            },
        }
    )

    return contract


def evals_agent(state: State) -> Dict[str, any]:
    """
    Evals agent - simplified to telemetry collection only.
    Architecture generation has moved to Design phase (output_formatter_node).
    """
    existing = state.get("eval_state")
    eval_state = _initial_eval_state(existing)

    # Get results from subnodes (simplified - telemetry only)
    telemetry_result = eval_state.get("telemetry", {})
    
    # Check status of telemetry subnode
    telemetry_status = telemetry_result.get("status", "").lower() if isinstance(telemetry_result, dict) else ""
    telemetry_completed = telemetry_status == "completed" or telemetry_status == "skipped"
    
    # If telemetry is not complete, routing will handle it
    if not telemetry_completed:
        return {
            "eval_state": eval_state,
        }
    
    # Telemetry is complete - aggregate results
    eval_state["telemetry"] = telemetry_result
    
    # Aggregate notes
    if isinstance(telemetry_result, dict):
        notes = telemetry_result.get("notes")
        if isinstance(notes, list):
            for note in notes:
                eval_state["notes"] = _append_eval_note(eval_state.get("notes", []), note)
        elif notes:
            eval_state["notes"] = _append_eval_note(eval_state.get("notes", []), notes)
    eval_state["status"] = telemetry_status if telemetry_status else "completed"
    existing_design_state = state.get("design_state") if isinstance(state.get("design_state"), dict) else {}
    updated_design_state = dict(existing_design_state)
    tmp_state: State = dict(state)  # type: ignore[assignment]
    tmp_state["eval_state"] = eval_state
    tmp_state["design_state"] = updated_design_state
    updated_design_state["asc_v1"] = _build_asc_v1(tmp_state)
    updated_design_state["asc_v11"] = _build_asc_v11(tmp_state)

    return {
        "eval_state": eval_state,
        "design_state": updated_design_state,
        "run_phase": "done",
    }
