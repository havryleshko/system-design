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
)

builder = StateGraph(State)

builder.add_node("orchestrator", orchestrator)
builder.add_node("planner_agent", planner_agent)
builder.add_node("planner_scope", planner_scope)
builder.add_node("planner_steps", planner_steps)
builder.add_node("research", research_agent)
builder.add_node("design", design_agent)
builder.add_node("critic", critic_agent)
builder.add_node("evals", evals_agent)

builder.add_edge(START, "orchestrator")

builder.add_edge("planner_agent", "orchestrator")
builder.add_edge("planner_agent", "planner_scope")
builder.add_edge("planner_agent", "planner_steps")
builder.add_edge("planner_scope", "planner_agent")
builder.add_edge("planner_steps", "planner_agent")
builder.add_edge("research_agent", "orchestrator")
builder.add_edge("research_agent", "knowledge_base_node")
builder.add_edge("research_agent", "github_api_node")
builder.add_edge("research_agent", "web_search_node")
builder.add_edge("knowledge_base_node", "research_agent")
builder.add_edge("github_api_node" "research agent")
builder.add_edge("web_search_node", "research_agent")
builder.add_edge("research_agent", "orchestrator")
builder.add_edge("design_agent", "orchestrator")
builder.add_edge("design_agent", "component_library_node")
builder.add_edge("design_agent", "diagram_generator_node")
builder.add_edge("design_agent", "cost_est_node")
builder.add_edge("component_library_node", "design_agent")
builder.add_edge("diagram_generator_node", "design_agent")
builder.add_edge("cost_est_node", "design_agent")
builder.add_edge("design_agent", "orchestrator")
builder.add_edge("critic", "orchestrator")
builder.add_edge("evals", "orchestrator")
builder.add_edge("orchestrator", END)


def _route_from_orchestrator(state: State) -> Literal["planner", "research", "design", "critic", "evals", "DONE"]:
    phase = (state.get("run_phase") or "planner").lower()
    if phase == "planner":
        return "planner"
    if phase == "research":
        return "research"
    if phase == "design":
        return "design"
    if phase == "critic":
        return "critic"
    if phase == "evals":
        return "evals"
    return "DONE"


builder.add_conditional_edges(
    "orchestrator",
    _route_from_orchestrator,
    {
        "planner": "planner_agent",
        "research": "research",
        "design": "design",
        "critic": "critic",
        "evals": "evals",
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
