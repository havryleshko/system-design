from typing import Optional
from app.schemas.runs import RunStart, RunStatus, RunTrace
from app.storage.memory import create_run as store_create_run, get_run as store_get_run, get_trace as store_get_trace

def start_run(body: RunStart) -> RunStatus:
    return store_create_run(body)

def fetch_status(run_id: str) -> Optional[RunStatus]:
    return store_get_run(run_id)

def fetch_trace(run_id: str) -> Optional[RunTrace]:
    return store_get_trace(run_id)