from __future__ import annotations
import os
import atexit
from functools import lru_cache
from contextlib import ExitStack
import logging
from urllib.parse import urlparse

from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver  # pyright: ignore[reportMissingImports]

from .state import State
from .nodes import (
    orchestrator,
    planner_agent,
    planner_scope,
    planner_steps,
    research_agent,
    design_agent,
    critic_agent,
    evals_agent,
    knowledge_base_node,
    github_api_node,
    web_search_node,
    component_library_node,
    diagram_generator_node,
    cost_est_node,
    review_node,
    hallucination_check_node,
    risk_node,
    telemetry_node,
    scores_node,
)

builder = StateGraph(State)

builder.add_node("orchestrator", orchestrator)
builder.add_node("planner_agent", planner_agent)
builder.add_node("planner_scope", planner_scope)
builder.add_node("planner_steps", planner_steps)
builder.add_node("research_agent", research_agent)
builder.add_node("design_agent", design_agent)
builder.add_node("critic_agent", critic_agent)
builder.add_node("evals_agent", evals_agent)
builder.add_node("knowledge_base_node", knowledge_base_node)
builder.add_node("github_api_node", github_api_node)
builder.add_node("web_search_node", web_search_node)
builder.add_node("component_library_node", component_library_node)
builder.add_node("diagram_generator_node", diagram_generator_node)
builder.add_node("cost_est_node", cost_est_node)
builder.add_node("review_node", review_node)
builder.add_node("hallucination_check_node", hallucination_check_node)
builder.add_node("risk_node", risk_node)
builder.add_node("telemetry_node", telemetry_node)
builder.add_node("scores_node", scores_node)
builder.add_edge(START, "orchestrator")

builder.add_edge("planner_agent", "orchestrator")
builder.add_edge("planner_agent", "planner_scope")
builder.add_edge("planner_agent", "planner_steps")
builder.add_edge("planner_scope", "planner_agent")
builder.add_edge("planner_steps", "planner_agent")

# research agent
builder.add_edge("research_agent", "orchestrator")
builder.add_edge("research_agent", "knowledge_base_node")
builder.add_edge("research_agent", "github_api_node")
builder.add_edge("research_agent", "web_search_node")
builder.add_edge("knowledge_base_node", "research_agent")
builder.add_edge("github_api_node", "research_agent")
builder.add_edge("web_search_node", "research_agent")

# design 
builder.add_edge("design_agent", "orchestrator")
builder.add_edge("design_agent", "component_library_node")
builder.add_edge("design_agent", "diagram_generator_node")
builder.add_edge("design_agent", "cost_est_node")
builder.add_edge("component_library_node", "design_agent")
builder.add_edge("diagram_generator_node", "design_agent")
builder.add_edge("cost_est_node", "design_agent")
builder.add_edge("design_agent", "orchestrator")

# critic agent
builder.add_edge("critic_agent", "orchestrator")
builder.add_edge("critic_agent", "review_node")
builder.add_edge("critic_agent", "hallucination_check_node")
builder.add_edge("critic_agent", "risk_node")
builder.add_edge("review_node", "critic_agent")
builder.add_edge("hallucination_check_node", "critic_agent")
builder.add_edge("risk_node", "critic_agent")

# evals  wiring
builder.add_edge("evals_agent", "telemetry_node")
builder.add_edge("telemetry_node", "evals_agent")
builder.add_edge("evals_agent", "scores_node")
builder.add_edge("scores_node", "evals_agent")
builder.add_edge("evals_agent", "orchestrator")
builder.add_edge("orchestrator", END)


def _route_from_orchestrator(state: State) -> Literal["planner_agent", "research_agent", "design_agent", "critic_agent", "evals_agent", "DONE"]:
    phase = (state.get("run_phase") or "planner").lower()
    if phase == "planner":
        return "planner_agent"
    if phase == "research":
        return "research_agent"
    if phase == "design":
        return "design_agent"
    if phase == "critic":
        return "critic_agent"
    if phase == "evals":
        return "evals_agent"
    return "DONE"


builder.add_conditional_edges(
    "orchestrator",
    _route_from_orchestrator,
    {
        "planner": "planner_agent",
        "research": "research_agent",
        "design": "design_agent",
        "critic": "critic_agent",
        "evals": "evals_agent",
        "DONE": END,
    },
)

_CHECKPOINTER_STACK = ExitStack()
atexit.register(_CHECKPOINTER_STACK.close)
logger = logging.getLogger("app.agent.system_design.graph")


@lru_cache(maxsize=1)
def _load_checkpointer() -> PostgresSaver:
    conn = os.getenv("LANGGRAPH_PG_URL")
    if not conn:
        raise RuntimeError("LANGGRAPH_PG_URL not configured")
    parsed = urlparse(conn)
    host = parsed.hostname or "unknown"
    logger.info("Initialising LangGraph Postgres checkpointer", {"host": host})
    try:
        saver = _CHECKPOINTER_STACK.enter_context(PostgresSaver.from_conn_string(conn))
        saver.setup()
        logger.info("LangGraph checkpointer ready", {"host": host})
        return saver
    except Exception:
        logger.exception("Failed to initialise LangGraph checkpointer", {"host": host})
        raise


graph = builder.compile() # for production, use checkpointer=_load_checkpointer()
