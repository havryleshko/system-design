from __future__ import annotations
from typing import Literal
import os
import atexit
from functools import lru_cache
from contextlib import ExitStack
import logging
from urllib.parse import urlparse

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver  # pyright: ignore[reportMissingImports]
from .state import State, MAX_ITERATIONS, CRITIC_TARGET, MAX_CRITIC_PASSES
from .nodes import intent, clarifier, planner, kb_search, web_search, designer, critic, finaliser 
# defining a graph with shared state
builder = StateGraph(State)

# registering nodes
builder.add_node("intent", intent)
builder.add_node("clarifier", clarifier)
builder.add_node("planner", planner)
builder.add_node("kb_search", kb_search)
builder.add_node("web_search", web_search)
builder.add_node("designer", designer)
builder.add_node("critic", critic)
builder.add_node("finaliser", finaliser)

builder.add_edge(START, "intent")

def route_from_intent(state: State) -> Literal["clarifier", "planner"]:
    missing = state.get("missing_fields") or []
    it = int(state.get("iterations", 0) or 0)
    if missing and it < MAX_ITERATIONS:
        return "clarifier"
    return "planner"

builder.add_conditional_edges(
    "intent", 
    route_from_intent,
    {"clarifier": "clarifier", "planner": "planner"},
)

# Clarifier funnels back into the main chain once the user has supplied enough context.
builder.add_edge("clarifier", "planner")


from .nodes import last_human_text


def route_from_planner(state: State) -> Literal["kb_search"]:
    return "kb_search"


def route_from_kb(state: State) -> Literal["web_search", "designer"]:
    user_msg = last_human_text(state.get("messages", []))
    trigger_keywords = ["web", "search", "google", "browse", "internet", "cite", "live"]
    use_web = any(keyword in user_msg.lower() for keyword in trigger_keywords)
    metadata = state.get("metadata", {}) or {}
    qualified = int(metadata.get("kb_qualified") or 0)
    required_hits = int(metadata.get("kb_required_hits") or 2)
    force_web_on_low = metadata.get("kb_force_web_on_low_results", False)

    if qualified < required_hits:
        if force_web_on_low:
            use_web = True
        else:
            use_web = False
    elif not use_web:
        use_web = False
    return "web_search" if use_web else "designer"


builder.add_conditional_edges(
    "planner",
    route_from_planner,
    {"kb_search": "kb_search"}
)

builder.add_conditional_edges(
    "kb_search",
    route_from_kb,
    {"web_search": "web_search", "designer": "designer"}
)

# after web_search always go to designer
builder.add_edge("web_search", "designer")
builder.add_edge("designer", "critic")


def route_from_critic(state: State) -> Literal["finaliser", "designer"]:
    score = float(state.get("critic_score") or 0)
    loops = int(state.get("critic_iterations") or 0)
    if score >= CRITIC_TARGET or loops >= MAX_CRITIC_PASSES:
        return "finaliser"
    return "designer"


builder.add_conditional_edges(
    "critic",
    route_from_critic,
    {"finaliser": "finaliser", "designer": "designer"}
)

builder.add_edge("finaliser", END)


_CHECKPOINTER_STACK = ExitStack()
atexit.register(_CHECKPOINTER_STACK.close)
logger = logging.getLogger("app.agent.system_design.graph")


@lru_cache(maxsize=1)
def _load_checkpointer() -> PostgresSaver:
    """
    Initialises the Postgres checkpointer once.

    Clarifier resumes (thread interrupts) require persistent checkpoints,
    so we fail fast if LANGGRAPH_PG_URL is missing or invalid rather than
    letting requests reach the resume endpoint and 404.
    """
    conn = os.getenv("LANGGRAPH_PG_URL")
    if not conn:
        raise RuntimeError("LANGGRAPH_PG_URL not configured; clarifier resume requires persistent checkpoints")
    parsed = urlparse(conn)
    host = parsed.hostname or "unknown"
    logger.info("Initialising LangGraph Postgres checkpointer", {"host": host})
    try:
        saver = _CHECKPOINTER_STACK.enter_context(PostgresSaver.from_conn_string(conn))
        # Ensure schema is ready before the first run triggers an interrupt.
        saver.setup()
        logger.info("LangGraph checkpointer ready", {"host": host})
        return saver
    except Exception:
        logger.exception("Failed to initialise LangGraph checkpointer", {"host": host})
        raise


graph = builder.compile(checkpointer=_load_checkpointer())
