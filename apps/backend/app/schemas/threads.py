from pydantic import BaseModel
from typing import Literal, Optional, Dict, Any


class ThreadCreate(BaseModel):
    pass  # No input needed, just creates a thread


class ThreadResponse(BaseModel):
    thread_id: str


class RunStartRequest(BaseModel):
    input: str


class RunStartResponse(BaseModel):
    run_id: str
    thread_id: str


class ThreadStateResponse(BaseModel):
    thread_id: str
    run_id: Optional[str] = None
    status: Literal["running", "completed", "failed", "queued"]
    values: Optional[Dict[str, Any]] = None
    output: Optional[str] = None


class ThreadListItem(BaseModel):
    thread_id: str
    title: str
    status: Literal["running", "completed", "failed", "queued"]
    created_at: Optional[str] = None


class ThreadListResponse(BaseModel):
    threads: list[ThreadListItem]
