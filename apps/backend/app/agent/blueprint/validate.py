from __future__ import annotations
from typing import Any
from .schema import Blueprint

def validate_blueprint(blueprint: Blueprint) -> tuple[bool, list[str]]:
    errors: list[str] = []
    agent_ids = [a.id for a in blueprint.agents]
    if len(set(agent_ids)) != len(agent_ids):
        errors.append("agents[].id must be unique")

    node_ids = [n.id for n in blueprint.graph.nodes]
    if len(set(node_ids)) != len(node_ids):
        errors.append("graph.nodes[].id must be unique")

    node_set = set(node_ids)
    for e in blueprint.graph.edges:
        if e.source not in node_set:
            errors.append(f"graph.edges has unknown source '{e.source}'")
        if e.target not in node_set:
            errors.append(f"graph.edges has unknown target '{e.target}'")
    agent_set = set(agent_ids)
    for n in blueprint.graph.nodes:
        if n.type == "agent":
            if not n.agent_id:
                errors.append(f"graph.nodes '{n.id}' is type=agent but missing agent_id")
            elif n.agent_id not in agent_set:
                errors.append(f"graph.nodes '{n.id}' references unknown agent_id '{n.agent_id}'")

    ep = blueprint.graph.entry_point
    if ep and ep not in node_set:
        errors.append(f"graph.entry_point '{ep}' is not a node id")

    for x in blueprint.graph.exit_points or []:
        if x not in node_set:
            errors.append(f"graph.exit_points contains unknown node id '{x}'")

    return (len(errors) == 0, errors)


def extract_blueprint_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["blueprint must be an object"]
    try:
        bp = Blueprint.model_validate(value)
    except Exception as exc:
        return [f"blueprint schema invalid: {str(exc)}"]
    ok, errs = validate_blueprint(bp)
    return [] if ok else errs

