
from typing import TypedDict, Literal, Optional, List

from pydantic import BaseModel, Field


class ArchitectureTradeoff(TypedDict, total=False):
    decision: str
    alternatives: list[str]
    why: str
class ArchitectureDecision(TypedDict, total=False):
    single_vs_multi: Literal["single", "multi"]
    architecture_type: str  
    architecture_type_reason: str  
    architecture_class: Literal[
        "hierarchical_orchestrator",
        "supervisor_worker",
        "planner_executor_evaluator_loop",
        "hybrid",
    ]
    architecture_class_reason: str
    tradeoffs: list[ArchitectureTradeoff]
    confidence: float 
    assumptions: list[str]  
    missing_info: list[str]  
    pattern_influences: list[str]  
    pattern_deviation_notes: list[str] 

class AgentToolAccess(TypedDict, total=False):

    tool_id: str  
    scopes: list[str]  
    usage_notes: str  


class AgentMemorySpec(TypedDict, total=False):
    type: Literal["short_term", "long_term", "episodic", "semantic", "shared"]
    purpose: str
    implementation_hint: str  


class AgentSpec(TypedDict, total=False):
    id: str  
    name: str  
    role: str  
    
    boundaries: list[str]  
    inputs: list[str] 
    outputs: list[str] 
    reports_to: Optional[str]  
    subagents: list[str]  

    model_class: Literal["frontier", "mid", "small", "embedding", "fine_tuned"]
    model_class_rationale: str  
    tools: list[AgentToolAccess]  
    memory: list[AgentMemorySpec] 
    orchestration_constraints: list[str]  

class GraphNode(TypedDict, total=False):
    """Node in the agent interaction graph."""
    id: str
    type: Literal["agent", "tool", "human", "external", "start", "end"]
    label: str
    agent_id: Optional[str]  


class GraphEdge(TypedDict, total=False):

    source: str
    target: str  
    edge_type: Literal["control", "data"] 
    label: str  
    condition: Optional[str]  


class LoopSpec(TypedDict, total=False):

    id: str
    name: str
    entry_node: str
    exit_node: str  
    max_iterations: Optional[int]
    termination_conditions: list[str]


class InteractionGraph(TypedDict, total=False):

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    loops: list[LoopSpec]
    entry_point: str  
    exit_points: list[str]  
    termination_conditions: list[str] 

class ToolAlternative(TypedDict, total=False):

    tool_id: str  
    reason: str  


class SelectedTool(TypedDict, total=False):

    id: str  
    display_name: str
    category: str
    default_choice_reason: str  
    alternatives: list[ToolAlternative]
    auth_config: Optional[dict]  
    failure_handling: str  
    agent_permissions: dict[str, list[str]]  


class ToolingSpec(TypedDict, total=False):

    tool_catalog_version: str  # "v1"
    tools: list[SelectedTool]

class DeployabilityConstraint(TypedDict, total=False):

    agent_id: str
    model_class: str
    estimated_latency_ms: Optional[int]
    estimated_cost_per_call: Optional[str]  
    scaling_notes: str
    failure_modes: list[str]
    safeguards: list[str]
    degrades_to: str
    recovery_strategy: str


class DeployabilityMatrix(TypedDict, total=False):

    constraints: list[DeployabilityConstraint]
    orchestration_platform: str  
    orchestration_platform_reason: str
    infrastructure_notes: list[str]


class ExecutionStep(TypedDict, total=False):
    order: int
    agent_id: str
    action: str  
    inputs_from: list[str] 
    outputs_to: list[str]  
    can_loop: bool
    human_checkpoint: bool  


class ExecutionFlow(TypedDict, total=False):

    steps: list[ExecutionStep]
    parallel_groups: list[list[str]]  
    critical_path: list[int]  

class ProductState(TypedDict, total=False):
    status: Literal["ready_to_build", "draft"]
    missing_for_ready: list[str] 
    assumptions_made: list[str]  
    confidence_score: float  

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


class InteractionEdge(TypedDict, total=False):
    source: str
    target: str
    kind: str
    label: str


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
    interactions: list[InteractionEdge]
    memory: MemoryArchitecture
    control_loop: ControlLoop
    bounded_autonomy: BoundedAutonomy
    evals: EvalsSelfCorrectness
    goal_decomposition: GoalDecomposition
    implementation_notes: list[str]
    start_simple_recommendation: str


class ASCKickoff(TypedDict, total=False):
    summary: str
    open_questions: list[str]
    risks: list[str]


class ASCResearch(TypedDict, total=False):
    highlights: list[str]
    citations: list[dict]
    risks: list[str]


class ASCTelemetry(TypedDict, total=False):
    telemetry: dict
    notes: list[str]
    status: str


class ASCQuality(TypedDict, total=False):
    critic: dict
    telemetry: ASCTelemetry


class ASCBuild(TypedDict, total=False):
    milestones: list[str]
    steps: list[dict]
    first_tasks: list[dict]


class AgentSystemContractV1(TypedDict, total=False):
    version: str
    generated_at: str  
    goal: str
    kickoff: ASCKickoff
    architecture: dict
    research: ASCResearch
    quality: ASCQuality
    build: ASCBuild


# ---------------------------------------------------------------------------
# ArchitectureSpec (structured output for architecture_generator_node)
# ---------------------------------------------------------------------------


class ArchitectureMemoryOwned(BaseModel):
    type: Literal["short_term", "long_term", "episodic", "semantic"] = "short_term"
    purpose: str = ""
    implementation: str = ""


class ArchitectureAgent(BaseModel):
    id: str = Field(..., description="unique agent id")
    name: str = Field(..., description="goal-specific agent name")
    responsibility: str = Field(..., description="what this agent does")
    tools: List[str] = Field(default_factory=list)
    subagents: List[str] = Field(default_factory=list)
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    memory_owned: List[ArchitectureMemoryOwned] = Field(default_factory=list)
    failure_modes: List[str] = Field(default_factory=list)
    safeguards: List[str] = Field(default_factory=list)
    degrades_to: str = ""


class ArchitectureTool(BaseModel):
    id: str
    name: str
    type: str = "other"
    io_schema: str = ""
    failure_handling: str = ""


class ArchitectureInteraction(BaseModel):
    source: str
    target: str
    kind: str = "delegates"
    label: Optional[str] = None


class ArchitectureSpec(BaseModel):
    architecture_class: Literal[
        "hierarchical_orchestrator",
        "supervisor_worker",
        "planner_executor_evaluator_loop",
        "hybrid",
    ]
    architecture_class_reason: str = ""
    tradeoffs: List[ArchitectureTradeoff] = Field(default_factory=list)
    overview: str = ""
    agents: List[ArchitectureAgent] = Field(default_factory=list)
    tools: List[ArchitectureTool] = Field(default_factory=list)
    interactions: List[ArchitectureInteraction] = Field(default_factory=list)
    memory: dict = Field(default_factory=dict)
    control_loop: dict = Field(default_factory=dict)
    bounded_autonomy: dict = Field(default_factory=dict)
    implementation_notes: List[str] = Field(default_factory=list)
    start_simple_recommendation: str = ""


class AgentSystemContractV11(TypedDict, total=False):
    version: str 
    generated_at: str  
    goal: str
    
    product_state: ProductState
    
    decision: ArchitectureDecision
    
    agents: list[AgentSpec]
    
    # Objective 3: Interaction Graph
    graph: InteractionGraph
    execution_flow: ExecutionFlow

    tooling: ToolingSpec
    
    deployability: DeployabilityMatrix
    

    kickoff: ASCKickoff
    research: ASCResearch
    quality: ASCQuality
    build: ASCBuild

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
            errors.append(f"Memory architecture should include {mem_type}")
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


def validate_asc_v11(asc: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    
    # Check version
    if asc.get("version") != "v1.1":
        errors.append(f"Expected version 'v1.1', got '{asc.get('version')}'")
    
    # Check Objective 1: Decision
    decision = asc.get("decision", {})
    if not decision.get("single_vs_multi"):
        errors.append("Missing decision.single_vs_multi (Objective 1)")
    if not decision.get("architecture_type"):
        errors.append("Missing decision.architecture_type (Objective 1)")
    if not decision.get("architecture_type_reason"):
        errors.append("Missing decision.architecture_type_reason (Objective 1)")
    if not decision.get("architecture_class"):
        errors.append("Missing decision.architecture_class (Objective 1)")
    if decision.get("architecture_class") == "hybrid" and not decision.get("architecture_class_reason"):
        errors.append("Missing decision.architecture_class_reason when decision.architecture_class=hybrid (Objective 1)")
    
    # Check Objective 2: Agents
    agents = asc.get("agents", [])
    if not agents:
        errors.append("No agents defined (Objective 2)")
    else:
        for agent in agents:
            if not agent.get("id"):
                errors.append(f"Agent missing id: {agent}")
            if not agent.get("role"):
                errors.append(f"Agent '{agent.get('id')}' missing role (Objective 2)")
            if not agent.get("boundaries"):
                errors.append(f"Agent '{agent.get('id')}' missing boundaries (Objective 2)")
            if not agent.get("model_class"):
                errors.append(f"Agent '{agent.get('id')}' missing model_class (Objective 4)")
    
    # Check Objective 3: Graph
    graph = asc.get("graph", {})
    if not graph.get("nodes"):
        errors.append("Missing graph.nodes (Objective 3)")
    if not graph.get("edges"):
        errors.append("Missing graph.edges (Objective 3)")
    if not graph.get("entry_point"):
        errors.append("Missing graph.entry_point (Objective 3)")
    
    # Check Objective 4: Tooling
    tooling = asc.get("tooling", {})
    if tooling.get("tool_catalog_version") != "v1":
        errors.append("Tooling must reference tool_catalog_version 'v1' (Objective 4)")
    
    # Cross-reference: agent tools must exist in tooling.tools
    tool_ids = {t.get("id") for t in tooling.get("tools", [])}
    for agent in agents:
        for tool_access in agent.get("tools", []):
            if tool_access.get("tool_id") not in tool_ids:
                errors.append(
                    f"Agent '{agent.get('id')}' references tool '{tool_access.get('tool_id')}' "
                    "not in tooling.tools"
                )
    
    # Check product state
    product_state = asc.get("product_state", {})
    if not product_state.get("status"):
        errors.append("Missing product_state.status")
    
    return (len(errors) == 0, errors)


def determine_product_state(asc: dict) -> ProductState:

    is_valid, errors = validate_asc_v11(asc)
    
    decision = asc.get("decision", {})
    missing_info = decision.get("missing_info", [])
    assumptions = decision.get("assumptions", [])
    
    # Draft if there are validation errors, missing info, or assumptions
    if not is_valid or missing_info or len(assumptions) > 3:
        return ProductState(
            status="draft",
            missing_for_ready=errors + missing_info,
            assumptions_made=assumptions,
            confidence_score=decision.get("confidence", 0.5)
        )
    
    return ProductState(
        status="ready_to_build",
        missing_for_ready=[],
        assumptions_made=assumptions,
        confidence_score=decision.get("confidence", 0.9)
    )
