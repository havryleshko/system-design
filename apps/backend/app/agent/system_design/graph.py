from __future__ import annotations
import inspect
import os
import time
from typing import Any, Callable, Literal
from functools import lru_cache

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from .state import State
from .reasoning import build_event, has_truncation_marker, should_add_event
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
    output_formatter_node,
    review_node,
    hallucination_check_node,
    risk_node,
    telemetry_node,
)

builder = StateGraph(State)

_NODE_AGENT_PHASE: dict[str, tuple[str, str]] = {
    "orchestrator": ("Orchestrator", "orchestrator"),
    "planner_agent": ("Planner", "planner"),
    "planner_scope": ("Planner", "planner"),
    "planner_steps": ("Planner", "planner"),
    "research_agent": ("Research", "research"),
    "pattern_selector_node": ("Research", "research"),
    "knowledge_base_node": ("Research", "research"),
    "github_api_node": ("Research", "research"),
    "web_search_node": ("Research", "research"),
    "design_agent": ("Design", "design"),
    "architecture_generator_node": ("Design", "design"),
    "output_formatter_node": ("Design", "design"),
    "critic_agent": ("Critic", "critic"),
    "review_node": ("Critic", "critic"),
    "hallucination_check_node": ("Critic", "critic"),
    "risk_node": ("Critic", "critic"),
    "evals_agent": ("Evals", "evals"),
    "telemetry_node": ("Evals", "evals"),
}


def _get_in(obj: Any, path: list[str]) -> Any:
    cur = obj
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


_STATUS_PATHS: dict[str, list[str]] = {
    # Planner
    "planner_agent": ["planner_state", "status"],
    "planner_scope": ["plan_scope", "status"],
    "planner_steps": ["plan_state", "status"],
    # Research
    "research_agent": ["research_state", "status"],
    "pattern_selector_node": ["research_state", "nodes", "pattern_selector", "status"],
    "knowledge_base_node": ["research_state", "nodes", "knowledge_base", "status"],
    "github_api_node": ["research_state", "nodes", "github_api", "status"],
    "web_search_node": ["research_state", "nodes", "web_search", "status"],
    # Design
    "design_agent": ["design_state", "status"],
    "architecture_generator_node": ["design_state", "architecture", "status"],
    "output_formatter_node": ["design_state", "output", "status"],
    # Critic
    "critic_agent": ["critic_state", "status"],
    "review_node": ["critic_state", "review", "status"],
    "hallucination_check_node": ["critic_state", "hallucination", "status"],
    "risk_node": ["critic_state", "risk", "status"],
    # Evals
    "evals_agent": ["eval_state", "status"],
    "telemetry_node": ["eval_state", "telemetry", "status"],
}


def _extract_status(node_name: str, out: dict) -> str:
    path = _STATUS_PATHS.get(node_name)
    if path:
        raw = _get_in(out, path)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().lower()
    raw2 = out.get("status") if isinstance(out, dict) else None
    if isinstance(raw2, str) and raw2.strip():
        return raw2.strip().lower()
    if node_name in {"orchestrator", "planner_agent", "research_agent", "design_agent", "critic_agent", "evals_agent"}:
        return "completed"
    return "unknown"


def _extract_node_result(node_name: str, out: dict) -> dict | None:
    if not isinstance(out, dict):
        return None
    node_paths: dict[str, list[str]] = {
        "orchestrator": ["orchestrator"],
        "planner_agent": ["planner_state"],
        "research_agent": ["research_state"],
        "design_agent": ["design_state"],
        "critic_agent": ["critic_state"],
        "evals_agent": ["eval_state"],
        # Planner subnodes
        "planner_scope": ["plan_scope"],
        "planner_steps": ["plan_state"],
        # Research subnodes
        "pattern_selector_node": ["research_state", "nodes", "pattern_selector"],
        "knowledge_base_node": ["research_state", "nodes", "knowledge_base"],
        "github_api_node": ["research_state", "nodes", "github_api"],
        "web_search_node": ["research_state", "nodes", "web_search"],
        # Design subnodes
        "architecture_generator_node": ["design_state", "architecture"],
        "output_formatter_node": ["design_state", "output"],
        # Critic subnodes
        "review_node": ["critic_state", "review"],
        "hallucination_check_node": ["critic_state", "hallucination"],
        "risk_node": ["critic_state", "risk"],
        # Evals subnodes
        "telemetry_node": ["eval_state", "telemetry"],
    }
    path = node_paths.get(node_name)
    if not path:
        return None
    val = _get_in(out, path)
    return val if isinstance(val, dict) else None


def _first_nonempty_str(*values: Any, max_len: int = 240) -> str | None:
    for v in values:
        if isinstance(v, str):
            text = v.strip()
            if text:
                return text[: max_len - 1].rstrip() + "…" if len(text) > max_len else text
    return None


def _summarize_note(value: Any) -> str | None:
    if isinstance(value, str):
        return _first_nonempty_str(value, max_len=240)
    if isinstance(value, list):
        for item in value:
            text = _first_nonempty_str(item, max_len=240)
            if text:
                return text
    return None


def _safe_len_list(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _derive_what_why(
    *,
    node: str,
    agent: str,
    phase: str,
    status: str,
    state: State,
    out_dict: dict,
    node_result: dict,
) -> tuple[str | None, str | None]:
    prev_phase = (state.get("run_phase") or "").strip().lower()
    next_phase = (out_dict.get("run_phase") or "").strip().lower() if isinstance(out_dict.get("run_phase"), str) else ""
    note = _summarize_note(node_result.get("notes"))
    reason = _first_nonempty_str(node_result.get("reason"), max_len=240)
    if node in {"planner_agent", "research_agent", "design_agent", "critic_agent", "evals_agent", "orchestrator"}:
        if next_phase and next_phase != prev_phase:
            what = f"Advanced run phase to '{next_phase}'"
            why_parts: list[str] = []
            if prev_phase:
                why_parts.append(f"Previous phase was '{prev_phase}'")
            if note:
                why_parts.append(note)
            return what, "; ".join(why_parts) or None
        what = "Updated run state"
        why = note or ("Maintained execution flow for this phase." if phase else None)
        return what, why
    if node == "planner_scope":
        scope = node_result
        issues = scope.get("issues") if isinstance(scope.get("issues"), list) else []
        blocking = scope.get("blocking_issues") if isinstance(scope.get("blocking_issues"), list) else []
        info = scope.get("info_issues") if isinstance(scope.get("info_issues"), list) else []
        what = "Analyzed scope and constraints"
        why_parts = []
        if blocking:
            why_parts.append(f"Found {len(blocking)} blocking issue(s)")
        if info:
            why_parts.append(f"Found {len(info)} info gap(s)")
        if issues and not (blocking or info):
            why_parts.append(f"Found {len(issues)} issue(s)")
        if note:
            why_parts.append(note)
        return what, "; ".join(why_parts) or None

    if node == "planner_steps":
        plan_state = node_result
        steps = plan_state.get("steps") if isinstance(plan_state.get("steps"), list) else []
        quality = plan_state.get("quality")
        what = "Generated implementation plan"
        why_parts = []
        if steps:
            why_parts.append(f"Produced {len(steps)} high-level step(s)")
        if isinstance(quality, (int, float)):
            why_parts.append(f"Plan quality score: {float(quality):.2f}")
        if note:
            why_parts.append(note)
        return what, "; ".join(why_parts) or None

    # Research subnodes
    if node in {"knowledge_base_node", "github_api_node", "web_search_node"}:
        src = _first_nonempty_str(node_result.get("source"), max_len=60) or node.replace("_node", "").replace("_", " ")
        highlights = _safe_len_list(node_result.get("highlights"))
        citations = _safe_len_list(node_result.get("citations"))
        risks = _safe_len_list(node_result.get("risks"))

        if status == "skipped":
            what = f"Skipped {src}"
            why = reason or note or "No results were available for this source."
            return what, why

        what = f"Collected context from {src}"
        why_parts = []
        if highlights:
            why_parts.append(f"{highlights} highlight(s)")
        if citations:
            why_parts.append(f"{citations} citation(s)")
        if risks:
            why_parts.append(f"{risks} risk(s) flagged")
        if note:
            why_parts.append(note)
        if reason:
            why_parts.append(reason)
        return what, "; ".join(why_parts) or None

    # Design subnodes
    if node == "output_formatter_node":
        what = "Formatted final output"
        why_parts: list[str] = []
        if note:
            why_parts.append(note)
        output = out_dict.get("output")
        if isinstance(output, str) and output.strip():
            why_parts.append("Generated a user-facing writeup")
        return what, "; ".join(why_parts) or None

    # Critic subnodes
    if node in {"review_node", "hallucination_check_node", "risk_node"}:
        notes = node_result.get("notes")
        notes_count = len(notes) if isinstance(notes, list) else (1 if isinstance(notes, str) and notes.strip() else 0)
        if node == "review_node":
            what = "Reviewed the design"
        elif node == "hallucination_check_node":
            what = "Checked for hallucinations and inconsistencies"
        else:
            what = "Assessed risks and safety constraints"
        why_parts = []
        if notes_count:
            why_parts.append(f"Produced {notes_count} note(s)")
        if note and (not isinstance(notes, str) or note != notes.strip()):
            why_parts.append(note)
        return what, "; ".join(why_parts) or None

    # Evals
    if node == "telemetry_node":
        telemetry = node_result.get("telemetry") if isinstance(node_result.get("telemetry"), dict) else {}
        what = "Estimated telemetry and cost"
        why_parts = []
        if telemetry:
            why_parts.append(f"Telemetry fields: {', '.join(sorted(list(telemetry.keys()))[:4])}")
        if note:
            why_parts.append(note)
        return what, "; ".join(why_parts) or None

    # Fallback
    fallback_what = _first_nonempty_str(node_result.get("source"), max_len=80)
    if fallback_what:
        fallback_what = f"Processed {fallback_what}"
    else:
        fallback_what = "Processed step"
    fallback_why = reason or note
    return fallback_what, fallback_why


def _extract_relevant_outputs(*, status: str, node_result: dict) -> dict:
    notes = node_result.get("notes")
    reason = node_result.get("reason")
    out: dict[str, Any] = {"status": status}
    if notes is not None:
        out["notes"] = notes
    if reason is not None:
        out["reason"] = reason
    for key in ("highlights", "citations", "risks"):
        if isinstance(node_result.get(key), list):
            out[f"{key}_count"] = len(node_result[key])
    return out


def trace_node(node_name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
    agent, phase = _NODE_AGENT_PHASE.get(node_name, ("Unknown", "unknown"))

    async def _run(state: State) -> dict:
        start = time.perf_counter()
        out = fn(state)
        if inspect.isawaitable(out):
            out = await out
        duration_ms = int((time.perf_counter() - start) * 1000)

        out_dict = out if isinstance(out, dict) else {}
        status = _extract_status(node_name, out_dict)

        node_result = _extract_node_result(node_name, out_dict) or {}
        what = node_result.get("what") if isinstance(node_result, dict) else None
        why = node_result.get("why") if isinstance(node_result, dict) else None
        alternatives = node_result.get("alternatives_considered") if isinstance(node_result, dict) else None

        inputs = {
            "goal": state.get("goal"),
            "run_phase": state.get("run_phase"),
        }
        outputs = _extract_relevant_outputs(status=status, node_result=node_result if isinstance(node_result, dict) else {})
        if not isinstance(what, str) or not what.strip() or not isinstance(why, str) or not why.strip():
            derived_what, derived_why = _derive_what_why(
                node=node_name,
                agent=agent,
                phase=phase,
                status=status,
                state=state,
                out_dict=out_dict,
                node_result=node_result if isinstance(node_result, dict) else {},
            )
            if not (isinstance(what, str) and what.strip()):
                what = derived_what
            if not (isinstance(why, str) and why.strip()):
                why = derived_why

        existing_trace = state.get("reasoning_trace")
        if not should_add_event(existing_trace, status=status, kind="node_end"):
            if not has_truncation_marker(existing_trace):
                marker = build_event(
                    node=node_name,
                    agent=agent,
                    phase=phase,
                    status="completed",
                    duration_ms=0,
                    kind="trace_truncated",
                    what="Trace truncated",
                    why="Maximum reasoning_trace event cap reached; further low-importance events were dropped.",
                )
                return {**out_dict, "reasoning_trace": [marker]}
            return out_dict

        ev = build_event(
            node=node_name,
            agent=agent,
            phase=phase,
            status=status,
            duration_ms=duration_ms,
            kind="node_end",
            what=what if isinstance(what, str) else None,
            why=why if isinstance(why, str) else None,
            alternatives_considered=alternatives if isinstance(alternatives, list) else None,
            inputs=inputs,
            outputs=outputs,
            debug={"output_keys": list(out_dict.keys())[:25]},
        )
        return {**out_dict, "reasoning_trace": [ev]}

    return _run


builder.add_node("orchestrator", trace_node("orchestrator", orchestrator))
builder.add_node("planner_agent", trace_node("planner_agent", planner_agent))
builder.add_node("planner_scope", trace_node("planner_scope", planner_scope))
builder.add_node("planner_steps", trace_node("planner_steps", planner_steps))
builder.add_node("research_agent", trace_node("research_agent", research_agent))
builder.add_node("design_agent", trace_node("design_agent", design_agent))
builder.add_node("critic_agent", trace_node("critic_agent", critic_agent))
builder.add_node("evals_agent", trace_node("evals_agent", evals_agent))
# Research phase subnodes
builder.add_node("pattern_selector_node", trace_node("pattern_selector_node", pattern_selector_node))
builder.add_node("knowledge_base_node", trace_node("knowledge_base_node", knowledge_base_node))
builder.add_node("github_api_node", trace_node("github_api_node", github_api_node))
builder.add_node("web_search_node", trace_node("web_search_node", web_search_node))
# Design phase subnodes
builder.add_node("architecture_generator_node", trace_node("architecture_generator_node", architecture_generator_node))
builder.add_node("output_formatter_node", trace_node("output_formatter_node", output_formatter_node))
# Critic phase subnodes
builder.add_node("review_node", trace_node("review_node", review_node))
builder.add_node("hallucination_check_node", trace_node("hallucination_check_node", hallucination_check_node))
builder.add_node("risk_node", trace_node("risk_node", risk_node))
# Evals phase subnodes
builder.add_node("telemetry_node", trace_node("telemetry_node", telemetry_node))
builder.add_edge(START, "orchestrator")

# Planner sequencing: planner_agent -> planner_scope -> planner_agent -> planner_steps -> planner_agent -> orchestrator
builder.add_edge("planner_scope", "planner_agent")
builder.add_edge("planner_steps", "planner_agent")

# Research sequencing: research_agent -> pattern_selector_node -> research_agent -> knowledge_base_node -> research_agent -> github_api_node -> research_agent -> web_search_node -> research_agent -> orchestrator
builder.add_edge("pattern_selector_node", "research_agent")
builder.add_edge("knowledge_base_node", "research_agent")
builder.add_edge("github_api_node", "research_agent")
builder.add_edge("web_search_node", "research_agent")

# Design sequencing: design_agent -> architecture_generator_node -> design_agent -> output_formatter_node -> design_agent -> orchestrator
builder.add_edge("architecture_generator_node", "design_agent")
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


def _route_from_design_agent(state: State) -> Literal["architecture_generator_node", "output_formatter_node", "orchestrator"]:
    design_state = state.get("design_state") or {}
    
    # Check status of each subnode
    architecture_status = design_state.get("architecture", {}).get("status", "").lower() if isinstance(design_state.get("architecture"), dict) else ""
    output_status = design_state.get("output", {}).get("status", "").lower() if isinstance(design_state.get("output"), dict) else ""
    
    architecture_completed = architecture_status == "completed" or architecture_status == "skipped"
    output_completed = output_status == "completed" or output_status == "skipped"
    
    # Route to architecture_generator_node first if not completed
    if not architecture_completed:
        return "architecture_generator_node"
    
    # Route to output_formatter_node if architecture is done but output is not
    if architecture_completed and not output_completed:
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
