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

class RunTrace(BaseModel):
    id: str
    events: List[RunEvent]
