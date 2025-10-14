from pydantic import BaseModel
from typing import Literal, List


class RunStart(BaseModel):
    input: str 

class RunStatus(BaseModel):
    id:str
    status: Literal["queued", "running", "completed", "failed"]

class RunEvent(BaseModel):
    ts_ms: int
    level: Literal["info", "warn", "error"]
    message: str
    data: dict | None = None

class RunTrace(BaseModel):
    id: str
    events: List[RunEvent]
