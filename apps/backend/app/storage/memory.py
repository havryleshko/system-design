from __future__ import annotations
from typing import List, Dict, Optional
from uuid import uuid4
from app.schemas.runs import RunStart, RunStatus, RunEvent, RunTrace

_RUNS: Dict[str, RunStatus] = {}
_EVENTS: Dict[str, List[RunEvent]] = {}
_THREADS: Dict[str, Dict[str, any]] = {}
_HISTORY: Dict[str, List[Dict[str, any]]] = {}

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
    if run_id not in _RUNS:
        return None
    return RunTrace(id=run_id, events=_EVENTS.get(run_id, []))


def create_thread() -> Dict[str, any]:
    thread_id = str(uuid4())
    state = {"id": thread_id, "values": {}, "metadata": {}, "next": None}
    _THREADS[thread_id] = state
    _HISTORY[thread_id] = [{"state": state, "checkpoint_id": "root"}]
    return {"thread_id": thread_id, "id": thread_id}


def get_thread_state(thread_id: str) -> Optional[Dict[str, any]]:
    state = _THREADS.get(thread_id)
    if not state:
        return None
    return state


def get_thread_history(thread_id: str) -> Optional[List[Dict[str, any]]]:
    return _HISTORY.get(thread_id)
