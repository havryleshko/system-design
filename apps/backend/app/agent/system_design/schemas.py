
from typing import TypedDict, Literal, Optional


# =============================================================================
# ASC v1.1 Schema - Agent System Contract
# =============================================================================
# The ASC is the single source of truth for Results V2.
# It must answer the 4 objectives:
#   1. Architecture Decision: single vs multi-agent, architecture type, rationale
#   2. Agent Decomposition: agents, boundaries, reporting relationships
#   3. Interaction & Control Flow: who calls whom, order, data flow, loops/termination
#   4. Deployability Constraints: per-agent model class, tool access, memory, orchestration
# =============================================================================


# -----------------------------------------------------------------------------
# Objective 1: Architecture Decision
# -----------------------------------------------------------------------------

class ArchitectureDecision(TypedDict, total=False):
    """Objective 1: Single vs multi-agent decision with rationale."""
    single_vs_multi: Literal["single", "multi"]
    architecture_type: str  # e.g., "supervisor", "react", "plan-and-execute", "reflection"
    architecture_type_reason: str  # Why this architecture type was chosen
    confidence: float  # 0.0 to 1.0
    assumptions: list[str]  # Assumptions made due to missing info
    missing_info: list[str]  # Information that would improve the design
    pattern_influences: list[str]  # Pattern IDs from agentic_patterns.json that influenced
    pattern_deviation_notes: list[str]  # Why the design deviates from pattern templates


# -----------------------------------------------------------------------------
# Objective 2 + 4: Agent Specification (Decomposition + Deployability)
# -----------------------------------------------------------------------------

class AgentToolAccess(TypedDict, total=False):
    """Tool access specification for an agent."""
    tool_id: str  # Must reference tool_catalog_v1.json
    scopes: list[str]  # Auth scopes needed (from catalog)
    usage_notes: str  # How this agent uses the tool


class AgentMemorySpec(TypedDict, total=False):
    """Memory specification for an agent."""
    type: Literal["short_term", "long_term", "episodic", "semantic", "shared"]
    purpose: str
    implementation_hint: str  # e.g., "Redis for session state"


class AgentSpec(TypedDict, total=False):
    """
    Agent specification combining Objective 2 (decomposition) and 
    Objective 4 (deployability constraints).
    """
    id: str  # Unique identifier
    name: str  # Human-readable name
    role: str  # Primary responsibility
    
    # Objective 2: Boundaries and relationships
    boundaries: list[str]  # What this agent is responsible for (and NOT responsible for)
    inputs: list[str]  # What inputs this agent receives
    outputs: list[str]  # What outputs this agent produces
    reports_to: Optional[str]  # Parent agent ID (for hierarchical architectures)
    subagents: list[str]  # Child agent IDs (for supervisor patterns)
    
    # Objective 4: Deployability constraints
    model_class: Literal["frontier", "mid", "small", "embedding", "fine_tuned"]
    model_class_rationale: str  # Why this model class was chosen
    tools: list[AgentToolAccess]  # Tools this agent can access
    memory: list[AgentMemorySpec]  # Memory this agent owns
    orchestration_constraints: list[str]  # e.g., "must complete within 30s", "requires human approval"


# -----------------------------------------------------------------------------
# Objective 3: Interaction Graph & Control Flow
# -----------------------------------------------------------------------------

class GraphNode(TypedDict, total=False):
    """Node in the agent interaction graph."""
    id: str
    type: Literal["agent", "tool", "human", "external", "start", "end"]
    label: str
    agent_id: Optional[str]  # Reference to AgentSpec.id if type="agent"


class GraphEdge(TypedDict, total=False):
    """Edge in the agent interaction graph."""
    source: str  # Node ID
    target: str  # Node ID
    edge_type: Literal["control", "data"]  # Control flow vs data flow
    label: str  # Description of what flows
    condition: Optional[str]  # Conditional edge (e.g., "if approved")


class LoopSpec(TypedDict, total=False):
    """Loop specification for iterative patterns."""
    id: str
    name: str
    entry_node: str  # Node ID where loop starts
    exit_node: str  # Node ID where loop ends
    max_iterations: Optional[int]
    termination_conditions: list[str]


class InteractionGraph(TypedDict, total=False):
    """Objective 3: Complete interaction and control flow specification."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    loops: list[LoopSpec]
    entry_point: str  # Starting node ID
    exit_points: list[str]  # Terminal node IDs
    termination_conditions: list[str]  # Global termination conditions


# -----------------------------------------------------------------------------
# Objective 4: Tool Catalog Integration
# -----------------------------------------------------------------------------

class ToolAlternative(TypedDict, total=False):
    """Alternative tool with rationale."""
    tool_id: str  # Must reference tool_catalog_v1.json
    reason: str  # Why this is a good alternative


class SelectedTool(TypedDict, total=False):
    """Tool selected from catalog with deployment details."""
    id: str  # Must match tool_catalog_v1.json
    display_name: str
    category: str
    default_choice_reason: str  # Why this was chosen as default
    alternatives: list[ToolAlternative]
    auth_config: Optional[dict]  # Auth configuration if needed
    failure_handling: str  # How to handle failures
    agent_permissions: dict[str, list[str]]  # agent_id -> list of scopes


class ToolingSpec(TypedDict, total=False):
    """Complete tooling specification for the architecture."""
    tool_catalog_version: str  # "v1"
    tools: list[SelectedTool]


# -----------------------------------------------------------------------------
# Objective 4: Deployability Matrix
# -----------------------------------------------------------------------------

class DeployabilityConstraint(TypedDict, total=False):
    """Deployability constraint for an agent."""
    agent_id: str
    model_class: str
    estimated_latency_ms: Optional[int]
    estimated_cost_per_call: Optional[str]  # e.g., "$0.01"
    scaling_notes: str
    failure_modes: list[str]
    recovery_strategy: str


class DeployabilityMatrix(TypedDict, total=False):
    """Objective 4: Complete deployability specification."""
    constraints: list[DeployabilityConstraint]
    orchestration_platform: str  # e.g., "langgraph"
    orchestration_platform_reason: str
    infrastructure_notes: list[str]


# -----------------------------------------------------------------------------
# Execution Flow (Objective 3 supplement)
# -----------------------------------------------------------------------------

class ExecutionStep(TypedDict, total=False):
    """Single step in the execution runbook."""
    order: int
    agent_id: str
    action: str  # What the agent does
    inputs_from: list[str]  # Where inputs come from (agent IDs or "user")
    outputs_to: list[str]  # Where outputs go (agent IDs or "user")
    can_loop: bool
    human_checkpoint: bool  # Requires human approval


class ExecutionFlow(TypedDict, total=False):
    """Ordered execution runbook derived from graph."""
    steps: list[ExecutionStep]
    parallel_groups: list[list[str]]  # Groups of step orders that can run in parallel
    critical_path: list[int]  # Step orders on critical path


# -----------------------------------------------------------------------------
# Product State
# -----------------------------------------------------------------------------

class ProductState(TypedDict, total=False):
    """Product state indicating readiness."""
    status: Literal["ready_to_build", "draft"]
    missing_for_ready: list[str]  # What's needed to reach ready_to_build
    assumptions_made: list[str]  # Assumptions that should be validated
    confidence_score: float  # 0.0 to 1.0


# -----------------------------------------------------------------------------
# Legacy Types (kept for backward compatibility)
# -----------------------------------------------------------------------------

class AgentRole(TypedDict, total=False):
    """Legacy: Use AgentSpec instead."""
    id: str
    name: str
    responsibility: str
    tools: list[str]
    subagents: list[str]


class ToolSpec(TypedDict, total=False):
    """Legacy: Use SelectedTool instead."""
    id: str
    name: str
    type: Literal["api", "db", "llm", "search", "file", "code", "other"]
    io_schema: str  
    auth_method: str  
    failure_handling: str  


class InteractionEdge(TypedDict, total=False):
    """Legacy: Use GraphEdge instead."""
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
    """Legacy architecture output - kept for backward compatibility."""
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


# -----------------------------------------------------------------------------
# ASC v1.1 - Agent System Contract (Complete)
# -----------------------------------------------------------------------------

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
    """
    ASC v1.0 - Legacy format.
    Use AgentSystemContractV11 for new implementations.
    """
    version: str  # "v1"
    generated_at: str  # ISO-8601 UTC timestamp
    goal: str
    kickoff: ASCKickoff
    architecture: dict
    research: ASCResearch
    quality: ASCQuality
    build: ASCBuild


class AgentSystemContractV11(TypedDict, total=False):
    """
    ASC v1.1 - Agent System Contract
    
    The single source of truth for Results V2, answering all 4 objectives:
    1. Architecture Decision
    2. Agent Decomposition  
    3. Interaction & Control Flow
    4. Deployability Constraints
    """
    version: str  # "v1.1"
    generated_at: str  # ISO-8601 UTC timestamp
    goal: str
    
    # Product state
    product_state: ProductState
    
    # Objective 1: Architecture Decision
    decision: ArchitectureDecision
    
    # Objective 2 + 4: Agent Specifications
    agents: list[AgentSpec]
    
    # Objective 3: Interaction Graph
    graph: InteractionGraph
    
    # Objective 3: Execution Flow (derived from graph)
    execution_flow: ExecutionFlow
    
    # Objective 4: Tooling (grounded to catalog)
    tooling: ToolingSpec
    
    # Objective 4: Deployability Matrix
    deployability: DeployabilityMatrix
    
    # Legacy fields for backward compatibility
    kickoff: ASCKickoff
    research: ASCResearch
    quality: ASCQuality
    build: ASCBuild


# -----------------------------------------------------------------------------
# Validation Functions
# -----------------------------------------------------------------------------

def validate_architecture_output(output: dict) -> tuple[bool, list[str]]:
    """Validate legacy architecture output."""
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
    """Check if architecture uses generic agent names."""
    agents = output.get("agents", [])
    if not agents:
        return True
    generic_names = {"planner", "executor", "critic", "agent", "coordinator", "worker"}
    agent_names = [a.get("name", "").lower() for a in agents]
    if all(name in generic_names or not name for name in agent_names):
        return True
    return False


def validate_asc_v11(asc: dict) -> tuple[bool, list[str]]:
    """
    Validate ASC v1.1 contract for completeness.
    Returns (is_valid, list of errors/warnings).
    """
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
    """
    Determine if ASC is ready_to_build or draft based on completeness.
    """
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
