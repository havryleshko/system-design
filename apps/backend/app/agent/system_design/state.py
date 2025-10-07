from typing import Annotated, TypedDict
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

MAX_ITERATIONS = 2