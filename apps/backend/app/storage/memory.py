from __future__ import annotations
from typing import Dict, List, Optional
from uuid import uuid4

from app.schemas.runs import RunEvent, RunStart, RunStatus, RunTrace

_RUNS: Dict[str, RunStatus] = {}
_EVENTS: Dict[str, List[RunEvent]] = {}
_TOKEN_USAGE: Dict[str, Dict[str, Dict[str, int]]] = {}

def create_run(payload: RunStart) -> RunStatus:
    run_id = str(uuid4())
    status = RunStatus(id=run_id, status="queued")
    _RUNS[run_id] = status
    _EVENTS[run_id] = [RunEvent(ts_ms=0, level="info", message=f"started: {payload.input}")]
    return status

def get_run(run_id: str) -> Optional[RunStatus]:
    return _RUNS.get(run_id)

def add_event(run_id: str, event: RunEvent) -> None:
    if run_id not in _EVENTS:
        _EVENTS[run_id] = []
    _EVENTS[run_id].append(event)

def get_trace(run_id: str) -> Optional[RunTrace]:
    # In the new LangGraph flow, we may receive a run_id originating from
    # the LangGraph runtime (not from our create_run helper). We still want
    # to serve any events we've captured for that run_id via add_event.
    if run_id not in _RUNS and run_id not in _EVENTS:
        return None
    return RunTrace(id=run_id, events=_EVENTS.get(run_id, []))


def record_node_tokens(
    run_id: str,
    node: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    if not run_id or not node:
        return

    safe_prompt = max(int(prompt_tokens or 0), 0)
    safe_completion = max(int(completion_tokens or 0), 0)
    safe_total = max(int(total_tokens or 0), safe_prompt + safe_completion)

    run_usage = _TOKEN_USAGE.setdefault(run_id, {})
    entry = run_usage.get(node)
    if not entry:
        entry = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        run_usage[node] = entry

    entry["prompt_tokens"] = max(0, entry.get("prompt_tokens", 0) + safe_prompt)
    entry["completion_tokens"] = max(0, entry.get("completion_tokens", 0) + safe_completion)
    entry["total_tokens"] = max(0, entry.get("total_tokens", 0) + safe_total)


def get_total_tokens(run_id: str) -> int:
    """Best-effort total tokens for a run (in-memory, process-local)."""
    if not run_id:
        return 0
    nodes = _TOKEN_USAGE.get(run_id, {}) or {}
    total = 0
    for entry in nodes.values():
        if isinstance(entry, dict):
            total += int(entry.get("total_tokens", 0) or 0)
    return max(0, total)
