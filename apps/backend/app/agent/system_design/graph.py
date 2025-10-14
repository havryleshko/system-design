from __future__ import annotations
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .state import State, MAX_ITERATIONS, CRITIC_TARGET, MAX_CRITIC_PASSES
from .nodes import intent, clarifier, planner, web_search, designer, critic, finaliser 

# defining a graph with shared state
builder = StateGraph(State)

# registering nodes
builder.add_node("intent", intent)
builder.add_node("clarifier", clarifier)
builder.add_node("planner", planner)
builder.add_node("web_search", web_search)
builder.add_node("designer", designer)
builder.add_node("critic", critic)
builder.add_node("finaliser", finaliser)

builder.add_edge(START, "intent")

def route_from_intent(state: State) -> Literal["clarifier", "planner"]:
    return "clarifier" if state.get("missing_fields") else "planner"

builder.add_conditional_edges(
    "intent", 
    route_from_intent,
    {"clarifier": "clarifier", "planner": "planner"},
)

def route_from_clarifier(state: State) -> Literal["clarifier", "planner"]:
    it = int(state.get("iterations", 0) or 0 )
    return "clarifier" if state.get("missing_fields") and it < MAX_ITERATIONS else "planner"

builder.add_conditional_edges(
    "clarifier",
    route_from_clarifier,
    {"clarifier": "clarifier", "planner": "planner"}
)


from .nodes import last_human_text

def route_from_planner(state: State) -> Literal["web_search", "designer"]:
    user_msg = last_human_text(state.get("messages", []))
    trigger_keywords = ["web", "cite", "search", "current data", "find online", "ground", "live"]
    use_web = any(keyword in user_msg.lower() for keyword in trigger_keywords)
    return "web_search" if use_web else "designer"


builder.add_conditional_edges(
    "planner",
    route_from_planner,
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

graph = builder.compile()
