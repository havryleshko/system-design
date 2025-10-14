from typing import Optional, Dict, Any, List
from app.schemas.runs import RunStart, RunStatus, RunTrace
from app.storage.memory import (
    create_run as store_create_run,
    get_run as store_get_run,
    get_trace as store_get_trace,
    create_thread as store_create_thread,
    get_thread_state as store_get_thread_state,
    get_thread_history as store_get_thread_history,
)

def start_run(body: RunStart) -> RunStatus:
    return store_create_run(body)

def fetch_status(run_id: str) -> Optional[RunStatus]:
    return store_get_run(run_id)

def fetch_trace(run_id: str) -> Optional[RunTrace]:
    return store_get_trace(run_id)


def create_thread() -> Dict[str, Any]:
    return store_create_thread()


def fetch_thread_state(thread_id: str) -> Optional[Dict[str, Any]]:
    return store_get_thread_state(thread_id)


def fetch_thread_history(thread_id: str) -> Optional[List[Dict[str, Any]]]:
    return store_get_thread_history(thread_id)