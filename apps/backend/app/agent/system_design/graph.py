from __future__ import annotations
from typing import Literal

from langgraph.graph import StateGraph, START, END

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
    final_judgement_node,
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
builder.add_node("final_judgement_node", final_judgement_node)
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

# Planner sequencing: planner_agent -> planner_scope -> planner_agent -> planner_steps -> planner_agent -> orchestrator
# Remove concurrent edges to avoid InvalidUpdateError
builder.add_edge("planner_scope", "planner_agent")
builder.add_edge("planner_steps", "planner_agent")

# Research sequencing: research_agent -> knowledge_base_node -> research_agent -> github_api_node -> research_agent -> web_search_node -> research_agent -> orchestrator
# Remove concurrent edges to avoid InvalidUpdateError
builder.add_edge("knowledge_base_node", "research_agent")
builder.add_edge("github_api_node", "research_agent")
builder.add_edge("web_search_node", "research_agent")

# Design sequencing: design_agent -> component_library_node -> design_agent -> diagram_generator_node -> design_agent -> cost_est_node -> design_agent -> orchestrator
# Remove concurrent edges to avoid InvalidUpdateError
builder.add_edge("component_library_node", "design_agent")
builder.add_edge("diagram_generator_node", "design_agent")
builder.add_edge("cost_est_node", "design_agent")

# Critic sequencing: critic_agent -> review_node -> critic_agent -> hallucination_check_node -> critic_agent -> risk_node -> critic_agent -> orchestrator
# Remove concurrent edges to avoid InvalidUpdateError
builder.add_edge("review_node", "critic_agent")
builder.add_edge("hallucination_check_node", "critic_agent")
builder.add_edge("risk_node", "critic_agent")

# Evals sequencing: evals_agent -> telemetry_node -> evals_agent -> scores_node -> evals_agent -> orchestrator
# Remove concurrent edges to avoid InvalidUpdateError
builder.add_edge("telemetry_node", "evals_agent")
builder.add_edge("scores_node", "evals_agent")
builder.add_edge("final_judgement_node", "evals_agent")
builder.add_edge("orchestrator", END)


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


def _route_from_research_agent(state: State) -> Literal["knowledge_base_node", "github_api_node", "web_search_node", "orchestrator"]:

    research_state = state.get("research_state") or {}
    nodes = research_state.get("nodes") or {}
    
    # Check status of each subnode
    kb_status = nodes.get("knowledge_base", {}).get("status", "").lower() if isinstance(nodes.get("knowledge_base"), dict) else ""
    github_status = nodes.get("github_api", {}).get("status", "").lower() if isinstance(nodes.get("github_api"), dict) else ""
    web_status = nodes.get("web_search", {}).get("status", "").lower() if isinstance(nodes.get("web_search"), dict) else ""
    
    kb_completed = kb_status == "completed" or kb_status == "skipped"
    github_completed = github_status == "completed" or github_status == "skipped"
    web_completed = web_status == "completed" or web_status == "skipped"
    
    # Route to knowledge_base_node first if not completed
    if not kb_completed:
        return "knowledge_base_node"
    
    # Route to github_api_node if kb is done but github is not
    if kb_completed and not github_completed:
        return "github_api_node"
    
    # Route to web_search_node if kb and github are done but web is not
    if kb_completed and github_completed and not web_completed:
        return "web_search_node"
    
    # All are done, route to orchestrator
    return "orchestrator"


def _route_from_design_agent(state: State) -> Literal["component_library_node", "diagram_generator_node", "cost_est_node", "orchestrator"]:

    design_state = state.get("design_state") or {}
    plan_state = state.get("plan_state") or {}
    
    # Get subnode order (same logic as _design_subnode_order)
    from .nodes import _plan_has_component_hints
    component_first = _plan_has_component_hints(plan_state)
    if component_first:
        subnode_order = ["component_library_node", "diagram_generator_node", "cost_est_node"]
    else:
        subnode_order = ["diagram_generator_node", "component_library_node", "cost_est_node"]
    
    # Check status of each subnode
    components_status = design_state.get("components", {}).get("status", "").lower() if isinstance(design_state.get("components"), dict) else ""
    diagram_status = design_state.get("diagram", {}).get("status", "").lower() if isinstance(design_state.get("diagram"), dict) else ""
    costs_status = design_state.get("costs", {}).get("status", "").lower() if isinstance(design_state.get("costs"), dict) else ""
    
    # Map node names to their status
    status_map = {
        "component_library_node": components_status,
        "diagram_generator_node": diagram_status,
        "cost_est_node": costs_status,
    }
    
    # Route to first incomplete subnode in order
    for node_name in subnode_order:
        node_status = status_map.get(node_name, "").lower()
        node_completed = node_status == "completed" or node_status == "skipped"
        if not node_completed:
            return node_name
    
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


def _route_from_evals_agent(state: State) -> Literal["telemetry_node", "scores_node", "final_judgement_node", "orchestrator"]:
    eval_state = state.get("eval_state") or {}
    
    # Check status of each subnode
    telemetry_status = eval_state.get("telemetry", {}).get("status", "").lower() if isinstance(eval_state.get("telemetry"), dict) else ""
    scores_status = eval_state.get("scores", {}).get("status", "").lower() if isinstance(eval_state.get("scores"), dict) else ""
    final_status = eval_state.get("final_judgement", {}).get("status", "").lower() if isinstance(eval_state.get("final_judgement"), dict) else ""
    
    telemetry_completed = telemetry_status == "completed" or telemetry_status == "skipped"
    scores_completed = scores_status == "completed" or scores_status == "skipped"
    final_completed = final_status == "completed" or final_status == "skipped"
    
    # Route to telemetry_node first if not completed
    if not telemetry_completed:
        return "telemetry_node"
    
    # Route to scores_node if telemetry is done but scores are not
    if telemetry_completed and not scores_completed:
        return "scores_node"

    # Route to final_judgement_node after telemetry and scores are done
    if telemetry_completed and scores_completed and not final_completed:
        return "final_judgement_node"
    
    # All are done, route to orchestrator
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
        "component_library_node": "component_library_node",
        "diagram_generator_node": "diagram_generator_node",
        "cost_est_node": "cost_est_node",
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
        "scores_node": "scores_node",
        "final_judgement_node": "final_judgement_node",
        "orchestrator": "orchestrator",
    },
)

graph = builder.compile()
