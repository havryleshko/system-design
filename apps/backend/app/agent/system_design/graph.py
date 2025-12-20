from __future__ import annotations
import os
from typing import Literal
from functools import lru_cache

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

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
    pattern_selector_node,
    knowledge_base_node,
    github_api_node,
    web_search_node,
    architecture_generator_node,
    diagram_generator_node,
    output_formatter_node,
    review_node,
    hallucination_check_node,
    risk_node,
    telemetry_node,
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
# Research phase subnodes
builder.add_node("pattern_selector_node", pattern_selector_node)
builder.add_node("knowledge_base_node", knowledge_base_node)
builder.add_node("github_api_node", github_api_node)
builder.add_node("web_search_node", web_search_node)
# Design phase subnodes
builder.add_node("architecture_generator_node", architecture_generator_node)
builder.add_node("diagram_generator_node", diagram_generator_node)
builder.add_node("output_formatter_node", output_formatter_node)
# Critic phase subnodes
builder.add_node("review_node", review_node)
builder.add_node("hallucination_check_node", hallucination_check_node)
builder.add_node("risk_node", risk_node)
# Evals phase subnodes
builder.add_node("telemetry_node", telemetry_node)
builder.add_edge(START, "orchestrator")

# Planner sequencing: planner_agent -> planner_scope -> planner_agent -> planner_steps -> planner_agent -> orchestrator
builder.add_edge("planner_scope", "planner_agent")
builder.add_edge("planner_steps", "planner_agent")

# Research sequencing: research_agent -> pattern_selector_node -> research_agent -> knowledge_base_node -> research_agent -> github_api_node -> research_agent -> web_search_node -> research_agent -> orchestrator
builder.add_edge("pattern_selector_node", "research_agent")
builder.add_edge("knowledge_base_node", "research_agent")
builder.add_edge("github_api_node", "research_agent")
builder.add_edge("web_search_node", "research_agent")

# Design sequencing: design_agent -> architecture_generator_node -> design_agent -> diagram_generator_node -> design_agent -> output_formatter_node -> design_agent -> orchestrator
builder.add_edge("architecture_generator_node", "design_agent")
builder.add_edge("diagram_generator_node", "design_agent")
builder.add_edge("output_formatter_node", "design_agent")

# Critic sequencing: critic_agent -> review_node -> critic_agent -> hallucination_check_node -> critic_agent -> risk_node -> critic_agent -> orchestrator
builder.add_edge("review_node", "critic_agent")
builder.add_edge("hallucination_check_node", "critic_agent")
builder.add_edge("risk_node", "critic_agent")

# Evals sequencing (simplified): evals_agent -> telemetry_node -> evals_agent -> orchestrator -> END
builder.add_edge("telemetry_node", "evals_agent")



def _route_from_orchestrator(state: State) -> Literal["planner_agent", "research_agent", "design_agent", "critic_agent", "evals_agent", "DONE"]:
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


def _route_from_planner_agent(state: State) -> Literal["planner_scope", "planner_steps", "orchestrator"]:
    """
    Route planner_agent to subnodes sequentially, then to orchestrator when done.
    Flow: planner_agent -> planner_scope -> planner_agent -> planner_steps -> planner_agent -> orchestrator
    """
    plan_scope = state.get("plan_scope") or {}
    plan_state = state.get("plan_state") or {}
    
    # Check if planner_scope has been completed
    # Status can be in plan_scope dict or at top level from previous return
    scope_status = plan_scope.get("status", "").lower() if isinstance(plan_scope, dict) else ""
    scope_completed = scope_status == "completed"
    
    # Check if planner_steps has been completed
    # Status can be in plan_state dict or at top level from previous return
    steps_status = plan_state.get("status", "").lower() if isinstance(plan_state, dict) else ""
    steps_completed = steps_status == "completed"
    
    # Route to planner_scope first if not completed
    if not scope_completed:
        return "planner_scope"
    
    # Route to planner_steps if scope is done but steps are not
    if scope_completed and not steps_completed:
        return "planner_steps"
    
    # Both are done, route to orchestrator (planner_agent will handle quality checks)
    return "orchestrator"


def _route_from_research_agent(state: State) -> Literal["pattern_selector_node", "knowledge_base_node", "github_api_node", "web_search_node", "orchestrator"]:
    research_state = state.get("research_state") or {}
    nodes = research_state.get("nodes") or {}
    
    # Check status of each subnode
    pattern_status = nodes.get("pattern_selector", {}).get("status", "").lower() if isinstance(nodes.get("pattern_selector"), dict) else ""
    kb_status = nodes.get("knowledge_base", {}).get("status", "").lower() if isinstance(nodes.get("knowledge_base"), dict) else ""
    github_status = nodes.get("github_api", {}).get("status", "").lower() if isinstance(nodes.get("github_api"), dict) else ""
    web_status = nodes.get("web_search", {}).get("status", "").lower() if isinstance(nodes.get("web_search"), dict) else ""
    
    pattern_completed = pattern_status == "completed" or pattern_status == "skipped"
    kb_completed = kb_status == "completed" or kb_status == "skipped"
    github_completed = github_status == "completed" or github_status == "skipped"
    web_completed = web_status == "completed" or web_status == "skipped"
    
    # Route to pattern_selector_node first if not completed
    if not pattern_completed:
        return "pattern_selector_node"
    
    # Route to knowledge_base_node if pattern is done but kb is not
    if pattern_completed and not kb_completed:
        return "knowledge_base_node"
    
    # Route to github_api_node if kb is done but github is not
    if pattern_completed and kb_completed and not github_completed:
        return "github_api_node"
    
    # Route to web_search_node if github is done but web is not
    if pattern_completed and kb_completed and github_completed and not web_completed:
        return "web_search_node"
    
    # All are done, route to orchestrator
    return "orchestrator"


def _route_from_design_agent(state: State) -> Literal["architecture_generator_node", "diagram_generator_node", "output_formatter_node", "orchestrator"]:
    design_state = state.get("design_state") or {}
    
    # Check status of each subnode
    architecture_status = design_state.get("architecture", {}).get("status", "").lower() if isinstance(design_state.get("architecture"), dict) else ""
    diagram_status = design_state.get("diagram", {}).get("status", "").lower() if isinstance(design_state.get("diagram"), dict) else ""
    output_status = design_state.get("output", {}).get("status", "").lower() if isinstance(design_state.get("output"), dict) else ""
    
    architecture_completed = architecture_status == "completed" or architecture_status == "skipped"
    diagram_completed = diagram_status == "completed" or diagram_status == "skipped"
    output_completed = output_status == "completed" or output_status == "skipped"
    
    # Route to architecture_generator_node first if not completed
    if not architecture_completed:
        return "architecture_generator_node"
    
    # Route to diagram_generator_node if architecture is done but diagram is not
    if architecture_completed and not diagram_completed:
        return "diagram_generator_node"
    
    # Route to output_formatter_node if diagram is done but output is not
    if architecture_completed and diagram_completed and not output_completed:
        return "output_formatter_node"
    
    # All are done, route to orchestrator
    return "orchestrator"


def _route_from_critic_agent(state: State) -> Literal["review_node", "hallucination_check_node", "risk_node", "orchestrator"]:
    critic_state = state.get("critic_state") or {}
    
    # Check status of each subnode
    review_status = critic_state.get("review", {}).get("status", "").lower() if isinstance(critic_state.get("review"), dict) else ""
    hallucination_status = critic_state.get("hallucination", {}).get("status", "").lower() if isinstance(critic_state.get("hallucination"), dict) else ""
    risk_status = critic_state.get("risk", {}).get("status", "").lower() if isinstance(critic_state.get("risk"), dict) else ""
    
    review_completed = review_status == "completed" or review_status == "skipped"
    hallucination_completed = hallucination_status == "completed" or hallucination_status == "skipped"
    risk_completed = risk_status == "completed" or risk_status == "skipped"
    
    # Route to review_node first if not completed
    if not review_completed:
        return "review_node"
    
    # Route to hallucination_check_node if review is done but hallucination is not
    if review_completed and not hallucination_completed:
        return "hallucination_check_node"
    
    # Route to risk_node if review and hallucination are done but risk is not
    if review_completed and hallucination_completed and not risk_completed:
        return "risk_node"
    
    # All are done, route to orchestrator
    return "orchestrator"


def _route_from_evals_agent(state: State) -> Literal["telemetry_node", "orchestrator"]:
    """
    Route evals_agent to subnodes sequentially (simplified - telemetry only):
    evals_agent -> telemetry_node -> evals_agent -> orchestrator -> END
    """
    eval_state = state.get("eval_state") or {}
    
    # Check status of telemetry subnode
    telemetry_status = eval_state.get("telemetry", {}).get("status", "").lower() if isinstance(eval_state.get("telemetry"), dict) else ""
    telemetry_completed = telemetry_status == "completed" or telemetry_status == "skipped"
    
    # Route to telemetry_node first if not completed
    if not telemetry_completed:
        return "telemetry_node"
    
    # Done, route to orchestrator
    return "orchestrator"


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

builder.add_conditional_edges(
    "planner_agent",
    _route_from_planner_agent,
    {
        "planner_scope": "planner_scope",
        "planner_steps": "planner_steps",
        "orchestrator": "orchestrator",
    },
)

builder.add_conditional_edges(
    "research_agent",
    _route_from_research_agent,
    {
        "pattern_selector_node": "pattern_selector_node",
        "knowledge_base_node": "knowledge_base_node",
        "github_api_node": "github_api_node",
        "web_search_node": "web_search_node",
        "orchestrator": "orchestrator",
    },
)

builder.add_conditional_edges(
    "design_agent",
    _route_from_design_agent,
    {
        "architecture_generator_node": "architecture_generator_node",
        "diagram_generator_node": "diagram_generator_node",
        "output_formatter_node": "output_formatter_node",
        "orchestrator": "orchestrator",
    },
)

builder.add_conditional_edges(
    "critic_agent",
    _route_from_critic_agent,
    {
        "review_node": "review_node",
        "hallucination_check_node": "hallucination_check_node",
        "risk_node": "risk_node",
        "orchestrator": "orchestrator",
    },
)

builder.add_conditional_edges(
    "evals_agent",
    _route_from_evals_agent,
    {
        "telemetry_node": "telemetry_node",
        "orchestrator": "orchestrator",
    },
)

# Compile graph without checkpointer - will be added at runtime
graph = builder.compile()

# Export the builder so we can compile with checkpointer at runtime
graph_builder = builder


_checkpointer_instance = None
_checkpointer_context = None

async def _load_checkpointer_async():
    """Load the async checkpointer for PostgreSQL."""
    global _checkpointer_instance, _checkpointer_context
    if _checkpointer_instance is not None:
        return _checkpointer_instance
    
    conn_str = os.getenv("LANGGRAPH_PG_URL")
    if not conn_str:
        raise RuntimeError("LANGGRAPH_PG_URL not configured")
    
    # AsyncPostgresSaver.from_conn_string returns an async context manager
    _checkpointer_context = AsyncPostgresSaver.from_conn_string(conn_str)
    _checkpointer_instance = await _checkpointer_context.__aenter__()
    await _checkpointer_instance.setup()
    return _checkpointer_instance


async def get_compiled_graph_with_checkpointer():
    """Get a compiled graph with the async checkpointer attached."""
    checkpointer = await _load_checkpointer_async()
    return graph_builder.compile(checkpointer=checkpointer)
