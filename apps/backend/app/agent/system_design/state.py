from typing import Annotated, TypedDict, Any, Dict
import operator
from langchain_core.messages import BaseMessage

class State(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], operator.add]
    goal: str
    missing_fields: Annotated[list[str], operator.add]
    iterations: int
    plan: str
    design: str
    output: str
    grounding_queries: Annotated[list[str], operator.add]
    grounding_snippets: Annotated[list[dict], operator.add]
    citations: Annotated[list[dict], operator.add]
    design_json: dict
    design_brief: str
    critic_score: float
    critic_notes: str
    critic_iterations: int
    critic_fixes: list[str]
    metadata: Dict[str, Any]

CRITIC_TARGET = 0.85
MAX_CRITIC_PASSES = 1

MAX_ITERATIONS = 2