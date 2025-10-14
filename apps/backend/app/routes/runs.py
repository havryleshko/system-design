from fastapi import APIRouter, HTTPException, status

from app.schemas.runs import RunStart, RunStatus, RunTrace
from app.services import runs as run_service

runs_router = APIRouter(prefix="/runs", tags=["runs"])
threads_router = APIRouter(prefix="/threads", tags=["threads"])


@runs_router.post("", status_code=status.HTTP_201_CREATED, response_model=RunStatus)
def create_run(payload: RunStart):
    return run_service.start_run(payload)


@runs_router.get("/{run_id}", response_model=RunStatus)
def get_run(run_id: str):
    status_payload = run_service.fetch_status(run_id)
    if not status_payload:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return status_payload


@runs_router.get("/{run_id}/trace", response_model=RunTrace)
def get_run_trace(run_id: str):
    trace = run_service.fetch_trace(run_id)
    if not trace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")
    return trace


@threads_router.post("", status_code=status.HTTP_201_CREATED)
def create_thread():
    return run_service.create_thread()


@threads_router.get("/{thread_id}/state")
def get_thread_state(thread_id: str):
    state = run_service.fetch_thread_state(thread_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread not found")
    return state


@threads_router.get("/{thread_id}/history")
def get_thread_history(thread_id: str):
    history = run_service.fetch_thread_history(thread_id)
    if history is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="thread history not found")
    return history
