from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from pydantic import BaseModel, Field

# Storage caps (MVP)
MAX_EVENTS = 250
# Keep debug payloads bounded even after redaction.
MAX_DEBUG_JSON_CHARS = 8_000
MAX_STRING_CHARS = 2_000
MAX_LIST_ITEMS = 50
MAX_DICT_ITEMS = 50


SENSITIVE_KEY_FRAGMENTS: tuple[str, ...] = (
    "authorization",
    "cookie",
    "token",
    "api_key",
    "apikey",
    "secret",
    "password",
    "session",
    "set-cookie",
    "github_token",
    "supabase",
)


class ReasoningEvent(BaseModel):
    ts_iso: str = Field(..., description="UTC ISO-8601 timestamp")
    node: str
    agent: str
    phase: str
    status: str  
    duration_ms: Optional[int] = None

    kind: str = "node_end" 
    what: Optional[str] = None
    why: Optional[str] = None
    alternatives_considered: Optional[list[dict]] = None
    inputs: Optional[dict] = None
    outputs: Optional[dict] = None
    debug: Optional[dict] = None
    error: Optional[str] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def truncate_str(value: str, max_chars: int = MAX_STRING_CHARS) -> str:
    if not isinstance(value, str):
        value = str(value)
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1] + "…"


def truncate_list(value: list, max_items: int = MAX_LIST_ITEMS) -> list:
    if not isinstance(value, list):
        return value
    if len(value) <= max_items:
        return value
    return value[:max_items] + [{"_truncated": True, "kept": max_items, "dropped": len(value) - max_items}]


def truncate_dict(value: dict, max_items: int = MAX_DICT_ITEMS) -> dict:
    if not isinstance(value, dict):
        return value
    if len(value) <= max_items:
        return value
    items = list(value.items())[:max_items]
    out = dict(items)
    out["_truncated"] = True
    out["_dropped_keys_count"] = len(value) - max_items
    return out


def _is_sensitive_key(key: str) -> bool:
    k = (key or "").lower()
    return any(fragment in k for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, (bool, int, float, str)):
        return truncate_str(obj) if isinstance(obj, str) else obj

    if isinstance(obj, bytes):
        return {"_bytes": True, "len": len(obj)}

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            ks = str(k)
            if _is_sensitive_key(ks):
                out[ks] = "[REDACTED]"
            else:
                out[ks] = redact(v)
        return truncate_dict(out)

    if isinstance(obj, (list, tuple, set)):
        return truncate_list([redact(v) for v in list(obj)])
    return truncate_str(str(obj), max_chars=512)


def _truncate_json_chars(obj: Any, max_chars: int = MAX_DEBUG_JSON_CHARS) -> Any:
    try:
        encoded = json.dumps(obj, ensure_ascii=False, default=str)
        if len(encoded) <= max_chars:
            return obj
    except Exception:
        # If it can't serialize, coerce to string
        return truncate_str(str(obj), max_chars=512)
    if isinstance(obj, dict):
        shrunk = truncate_dict(obj, max_items=25)
        return _truncate_json_chars(shrunk, max_chars=max_chars)
    if isinstance(obj, list):
        shrunk = truncate_list(obj, max_items=25)
        return _truncate_json_chars(shrunk, max_chars=max_chars)
    if isinstance(obj, str):
        return truncate_str(obj, max_chars=max_chars)
    return truncate_str(str(obj), max_chars=512)


def build_event(
    *,
    node: str,
    agent: str,
    phase: str,
    status: str,
    duration_ms: Optional[int] = None,
    kind: str = "node_end",
    what: Optional[str] = None,
    why: Optional[str] = None,
    alternatives_considered: Optional[list[dict]] = None,
    inputs: Optional[dict] = None,
    outputs: Optional[dict] = None,
    debug: Optional[dict] = None,
    error: Optional[str] = None,
) -> dict:
    event = ReasoningEvent(
        ts_iso=_utc_now_iso(),
        node=str(node),
        agent=str(agent),
        phase=str(phase),
        status=str(status),
        duration_ms=duration_ms,
        kind=str(kind),
        what=truncate_str(what, max_chars=800) if isinstance(what, str) else what,
        why=truncate_str(why, max_chars=1200) if isinstance(why, str) else why,
        alternatives_considered=truncate_list(alternatives_considered or [], max_items=10) or None,
        inputs=_truncate_json_chars(redact(inputs)) if inputs is not None else None,
        outputs=_truncate_json_chars(redact(outputs)) if outputs is not None else None,
        debug=_truncate_json_chars(redact(debug)) if debug is not None else None,
        error=truncate_str(error, max_chars=800) if isinstance(error, str) else error,
    )
    return event.model_dump(exclude_none=True)


def should_add_event(existing_trace: Any, *, status: str, kind: str) -> bool:
    trace = existing_trace if isinstance(existing_trace, list) else []
    if len(trace) < MAX_EVENTS:
        return True
    if kind in ("trace_truncated", "run_failed"):
        return True
    if (status or "").lower() == "failed":
        return True
    return False


def has_truncation_marker(existing_trace: Any) -> bool:
    trace = existing_trace if isinstance(existing_trace, list) else []
    for ev in trace:
        if isinstance(ev, dict) and ev.get("kind") == "trace_truncated":
            return True
    return False


