"""Data models for Tortus semantic graph and traversal boundaries.

Provides Pydantic structures for documents, nodes, edges, search results,
and policy configurations to enforce strongly-typed traversal.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NodeKind(StrEnum):
    """Enumeration of possible semantic node types."""

    CONCEPT = "concept"
    CHUNK = "chunk"
    CLAIM = "claim"
    DECISION = "decision"
    API = "api"
    INCIDENT = "incident"


class EdgeType(StrEnum):
    """Enumeration of valid semantic edge relationships."""

    RELATED_TO = "related_to"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    CAUSED_BY = "caused_by"
    IMPLEMENTS = "implements"
    ADJACENT_TO = "adjacent_to"
    PORTAL = "portal"


class Document(BaseModel):
    """A source document containing raw text and metadata."""

    id: str
    title: str
    source: str
    domain: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceSpan(BaseModel):
    """A traceable segment of source text that supports a node or edge."""

    uri: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str

    @field_validator("end")
    @classmethod
    def end_must_follow_start(cls, end: int, info: Any) -> int:
        """Ensure the evidence span ends after it begins.

        Args:
            end: The ending character index.
            info: Context dictionary from Pydantic containing the 'start' field.

        Returns:
            The validated ending index.

        Raises:
            ValueError: If the end index is less than the start index.

        """
        start = info.data.get("start", 0)
        if end < start:
            raise ValueError("evidence span end must be >= start")
        return end


class Chunk(BaseModel):
    """A sequence of text derived from a parent Document."""

    id: str
    document_id: str
    title: str
    domain: str
    text: str
    evidence: EvidenceSpan
    ordinal: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SubgraphMembership(BaseModel):
    """Weighted membership defining a node's affinity to a specific domain or tenant."""

    subgraph: str
    weight: float = Field(ge=0.0, le=1.0)


class TorusCoordinate(BaseModel):
    """2D coordinate representing a node's location on the semantic torus."""

    theta: float = Field(ge=0.0)
    phi: float = Field(ge=0.0)


class ConceptNode(BaseModel):
    """A fundamental entity within the semantic graph."""

    id: str
    label: str
    kind: NodeKind = NodeKind.CONCEPT
    text: str
    chunk_id: str
    document_id: str
    memberships: list[SubgraphMembership] = Field(default_factory=list)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    torus: TorusCoordinate | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SemanticEdge(BaseModel):
    """A typed relationship connecting two nodes within the graph."""

    id: str
    source: str
    target: str
    edge_type: EdgeType
    weight: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PortalEdge(SemanticEdge):
    """A specialized edge indicating a bounded jump across different subgraphs."""

    edge_type: EdgeType = EdgeType.PORTAL
    source_subgraph: str
    target_subgraph: str


class TraversalPolicy(BaseModel):
    """Configuration limiting the latency, cost, and depth of graph traversal."""

    max_hops: int = Field(default=3, ge=0, le=8)
    max_nodes: int = Field(default=64, ge=1, le=1000)
    max_portal_hops: int = Field(default=5, ge=0, le=64)
    max_ms: int = Field(default=1500, ge=1)
    max_tokens: int = Field(default=2500, ge=128)
    local_only: bool = False
    explain_hops: bool = True
    semantic_group: str | None = None
    portal_preference: str | None = None


class SearchHit(BaseModel):
    """A candidate node returned by the initial vector-based seed search."""

    node_id: str
    label: str
    score: float
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    score_components: dict[str, float] = Field(default_factory=dict)


class ReasoningHop(BaseModel):
    """An explained step from one concept to another used to answer a query."""

    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    edge_type: EdgeType
    weight: float
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    score: float = 0.0
    reason: str = ""
    matched_terms: list[str] = Field(default_factory=list)
    torus_distance: float | None = None
    score_components: dict[str, float] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True)


class PrunedCandidate(BaseModel):
    """A traversal candidate that was considered but not selected."""

    from_node: str
    to_node: str
    edge_type: EdgeType
    score: float = 0.0
    reason: str
    matched_terms: list[str] = Field(default_factory=list)
    torus_distance: float | None = None
    score_components: dict[str, float] = Field(default_factory=dict)


class PortalDecision(BaseModel):
    """A selected or rejected portal traversal decision."""

    from_node: str
    to_node: str
    selected: bool
    score: float = 0.0
    reason: str
    matched_terms: list[str] = Field(default_factory=list)
    score_components: dict[str, float] = Field(default_factory=dict)


class AnswerClaim(BaseModel):
    """A sentence-level answer claim with evidence support telemetry."""

    text: str
    supported: bool
    support_count: int = 0
    evidence_uris: list[str] = Field(default_factory=list)


class RetrievalTrace(BaseModel):
    """Typed diagnostics for a full retrieval and synthesis run."""

    query_terms: list[str] = Field(default_factory=list)
    seed_hits: list[SearchHit] = Field(default_factory=list)
    selected_hops: list[ReasoningHop] = Field(default_factory=list)
    pruned_candidates: list[PrunedCandidate] = Field(default_factory=list)
    portal_decisions: list[PortalDecision] = Field(default_factory=list)
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    answer_claims: list[AnswerClaim] = Field(default_factory=list)
    unsupported_claims: list[AnswerClaim] = Field(default_factory=list)


class BudgetStats(BaseModel):
    """Telemetry detailing the resources consumed during graph traversal."""

    elapsed_ms: float
    nodes_visited: int
    hops_taken: int
    portal_hops: int = 0
    shard_fanout: int = 0
    shard_crossings: int = 0
    tokens_estimated: int
    candidates_considered: int = 0
    pruned_edges: int = 0
    portal_candidates: int = 0
    lexical_support: int = 0
    truncated: bool = False


class BaselineComparison(BaseModel):
    """Analytical data mapping performance differences against alternate retrieval strategies."""

    name: str
    hits: list[SearchHit]
    latency_ms: float


class AnswerResult(BaseModel):
    """The final synthesized response and reasoning trace provided to the caller."""

    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_path: list[ReasoningHop] = Field(default_factory=list)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    budget: BudgetStats
    warnings: list[str] = Field(default_factory=list)
    baseline_comparison: list[BaselineComparison] = Field(default_factory=list)
    trace: RetrievalTrace = Field(default_factory=RetrievalTrace)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
