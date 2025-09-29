from __future__ import annotations
from typing import Literal
from langgraph.graph import StateGraph, START, END
from .state import State, MAX_ITERATIONS
from .nodes import intent, clarifier, planner, designer, finaliser


#defining a graph with shared state
builder = StateGraph(State)

#registering nodes
builder.add_node("intent", intent)
builder.add_node("clarifier", clarifier)
builder.add_node("planner", planner)
builder.add_node("designer", designer)
builder.add_node("finaliser", finaliser)

builder.add_edge(START, "intent")

def route_from_intent(state: State) -> Literal["clarifier", "planner"]:

    return "clarifier" if state.get("missing_fields") else "planner" # if missing fiels -> clarifier, else continue planner

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

builder.add_edge("planner", "designer")
builder.add_edge("designer", "finaliser")
builder.add_edge("finaliser", END)


graph = builder.compile()

