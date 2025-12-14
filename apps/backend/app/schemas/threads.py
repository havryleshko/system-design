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
    final_judgement: Optional[str] = None
    output: Optional[str] = None
