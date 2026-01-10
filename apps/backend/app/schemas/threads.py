from pydantic import BaseModel
from typing import Literal, Optional, Dict, Any, List


class ThreadCreate(BaseModel):
    pass  # No input needed, just creates a thread


class ThreadResponse(BaseModel):
    thread_id: str


class RunStartRequest(BaseModel):
    input: str
    clarifier_session_id: Optional[str] = None
    clarifier_summary: Optional[str] = None


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

 
# =============================================================================
# Clarifier Chat (LLM-led) Schemas
# =============================================================================

class ClarifierSessionCreateRequest(BaseModel):
    input: str


class ClarifierSessionCreateResponse(BaseModel):
    session_id: str
    status: Literal["active"]
    assistant_message: str
    questions: Optional[List[Dict[str, Any]]] = None  # v2 expects 0 or 1 question
    turn_count: int


class ClarifierTurnRequest(BaseModel):
    message: str


class ClarifierTurnResponse(BaseModel):
    status: Literal["active", "finalized"]
    assistant_message: str
    questions: Optional[List[Dict[str, Any]]] = None  # v2 expects 0 or 1 question
    turn_count: int


class ClarifierFinalizeRequest(BaseModel):
    proceed_as_draft: bool


class ClarifierFinalizeResponse(BaseModel):
    status: Literal["ready", "draft"]
    final_summary: str
    enriched_prompt: str
    missing_fields: List[str]
    assumptions: List[str]


class ClarifierMessage(BaseModel):
    role: Literal["system", "assistant", "user"]
    content: str
    created_at: Optional[str] = None


class ClarifierSessionGetResponse(BaseModel):
    session_id: str
    thread_id: str
    status: Literal["active", "finalized", "abandoned"]
    original_input: str
    turn_count: int
    final_summary: Optional[str] = None
    enriched_prompt: Optional[str] = None
    missing_fields: List[str] = []
    assumptions: List[str] = []
    messages: List[ClarifierMessage] = []
