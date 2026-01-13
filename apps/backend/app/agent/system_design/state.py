from typing import Annotated, TypedDict, Any, Dict
import operator
from langchain_core.messages import BaseMessage


def overwrite(_: Any, updated: Any) -> Any:
    return updated

class State(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], operator.add]
    stream_messages: Annotated[list[BaseMessage], overwrite]
    reasoning_trace: Annotated[list[dict], operator.add]
    goal: str
    clarifier_done: Annotated[bool, overwrite]
    plan: str
    plan_quality: float
    plan_state: Dict[str, Any]
    plan_scope: Dict[str, Any]
    research_state: Dict[str, Any]
    research_summary: str
    research_highlights: Annotated[list[str], operator.add]
    research_citations: Annotated[list[dict], operator.add]
    selected_patterns: list[dict]
    design_state: Dict[str, Any]
    critic_state: Dict[str, Any]
    eval_state: Dict[str, Any]
    orchestrator: Dict[str, Any]
    run_phase: str
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
    architecture_json: dict
    agentic_architecture: Dict[str, Any]
    architecture_output: Dict[str, Any]
    # New canonical output for the UI (replaces asc_v11 and any ASC contracts)
    blueprint: Dict[str, Any]
    metadata: Dict[str, Any]

CRITIC_TARGET = 0.8
MAX_CRITIC_PASSES = 1