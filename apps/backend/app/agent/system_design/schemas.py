
from typing import TypedDict, Literal, Optional


class AgentRole(TypedDict, total=False):
    id: str
    name: str
    responsibility: str
    tools: list[str]
    subagents: list[str]


class ToolSpec(TypedDict, total=False):

    id: str
    name: str
    type: Literal["api", "db", "llm", "search", "file", "code", "other"]
    io_schema: str  
    auth_method: str  
    failure_handling: str  


class MemoryConfig(TypedDict, total=False):
    purpose: str
    implementation: str


class MemoryArchitecture(TypedDict, total=False):
    short_term: MemoryConfig
    long_term: MemoryConfig
    episodic: MemoryConfig
    semantic: MemoryConfig


class ControlLoop(TypedDict, total=False):
    flow: str 
    termination_conditions: list[str]


class BoundedAutonomyConstraint(TypedDict, total=False):

    constraint: str  
    value: str  
    action_on_breach: str  


class BoundedAutonomy(TypedDict, total=False):
    constraints: list[BoundedAutonomyConstraint]
    permission_gates: list[str]
    human_in_loop: list[str] 


class EvalsSelfCorrectness(TypedDict, total=False):
    critic_config: dict 
    external_validators: list[str]


class GoalDecomposition(TypedDict, total=False):

    high_level_objective: str
    intermediate_milestones: list[str]
    atomic_tasks: list[dict] 


class ArchitectureOutput(TypedDict, total=False):
    overview: str
    agents: list[AgentRole]
    tools: list[ToolSpec]
    memory: MemoryArchitecture
    control_loop: ControlLoop
    bounded_autonomy: BoundedAutonomy
    evals: EvalsSelfCorrectness
    goal_decomposition: GoalDecomposition
    diagram_mermaid: str
    diagram_image_url: str
    implementation_notes: list[str]
    start_simple_recommendation: str


def validate_architecture_output(output: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not output.get("agents"):
        errors.append("Architecture must have at least one agent")
    elif len(output.get("agents", [])) < 2:
        errors.append("Architecture should have at least 2 agents for meaningful separation of concerns")
    generic_names = {"planner", "executor", "critic", "agent"}
    agents = output.get("agents", [])
    for agent in agents:
        name = (agent.get("name") or "").lower()
        if name in generic_names:
            errors.append(f"Agent name '{agent.get('name')}' is too generic - use goal-specific names")
    if not output.get("tools"):
        errors.append("Architecture should have at least one tool defined")
    memory = output.get("memory", {})
    required_memory_types = ["short_term", "long_term"]
    for mem_type in required_memory_types:
        if not memory.get(mem_type):
            errors.append(f"Memory architecture should include {mem_type}"
    return (len(errors) == 0, errors)


def is_generic_architecture(output: dict) -> bool:
    agents = output.get("agents", [])
    if not agents:
        return True
    generic_names = {"planner", "executor", "critic", "agent", "coordinator", "worker"}
    agent_names = [a.get("name", "").lower() for a in agents]
    if all(name in generic_names or not name for name in agent_names):
        return True
    return False

