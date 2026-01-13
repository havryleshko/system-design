from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class BlueprintToolAccess(BaseModel):
    tool_id: str = Field(..., min_length=1)
    scopes: list[str] = Field(default_factory=list)
    usage_notes: Optional[str] = None


class BlueprintAgent(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)

    responsibilities: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)

    reports_to: Optional[str] = None
    subagents: list[str] = Field(default_factory=list)

    model: Optional[str] = None
    tools: list[BlueprintToolAccess] = Field(default_factory=list)


class BlueprintGraphNode(BaseModel):
    id: str = Field(..., min_length=1)
    type: Literal["agent", "start", "end"] = "agent"
    label: Optional[str] = None
    agent_id: Optional[str] = None


class BlueprintGraphEdge(BaseModel):
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    kind: Literal["control", "data", "hitl"] = "control"
    label: Optional[str] = None
    condition: Optional[str] = None


class BlueprintGraph(BaseModel):
    nodes: list[BlueprintGraphNode] = Field(default_factory=list)
    edges: list[BlueprintGraphEdge] = Field(default_factory=list)
    entry_point: Optional[str] = None
    exit_points: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _basic_graph_sanity(self) -> "BlueprintGraph":
        # Keep this validation extremely lightweight; deeper validation lives elsewhere.
        if not self.nodes:
            raise ValueError("graph.nodes must be a non-empty list")
        if not self.edges:
            raise ValueError("graph.edges must be a non-empty list")
        return self


class Blueprint(BaseModel):
    version: Literal["v1"] = "v1"
    generated_at: str = Field(..., description="UTC ISO-8601 timestamp")
    goal: str = Field(..., min_length=1)

    agents: list[BlueprintAgent] = Field(default_factory=list)
    graph: BlueprintGraph

    @model_validator(mode="after")
    def _basic_sanity(self) -> "Blueprint":
        if not self.agents:
            raise ValueError("agents must be a non-empty list")
        return self

