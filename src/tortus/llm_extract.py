"""Optional LLM-backed graph extraction layered over deterministic extraction."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .config import Settings
from .extract import extract_graph, stable_id
from .llm import build_llm_provider, cached_json_completion, provider_allowed
from .models import (
    Chunk,
    ConceptNode,
    EdgeType,
    SemanticEdge,
    SubgraphMembership,
)
from .text import important_terms, noun_phrases

LLM_EXTRACTION_SCHEMA_VERSION = "llm-extraction-v1"


class LLMConcept(BaseModel):
    """A concept proposed by the LLM extractor."""

    label: str = Field(min_length=2, max_length=96)
    kind: str = "concept"
    summary: str = Field(min_length=2, max_length=600)
    confidence: float = Field(default=0.72, ge=0.0, le=1.0)


class LLMRelation(BaseModel):
    """A relation proposed by the LLM extractor using concept labels."""

    source_label: str
    target_label: str
    edge_type: str = "related_to"
    rationale: str = ""
    confidence: float = Field(default=0.65, ge=0.0, le=1.0)


class LLMChunkGraph(BaseModel):
    """Schema-validated LLM extraction payload for one chunk."""

    concepts: list[LLMConcept] = Field(default_factory=list, max_length=6)
    relations: list[LLMRelation] = Field(default_factory=list, max_length=10)
    warnings: list[str] = Field(default_factory=list, max_length=6)


def extract_graph_with_settings(
    chunks: list[Chunk],
    settings: Settings,
) -> tuple[list[ConceptNode], list[SemanticEdge]]:
    """Extract a graph, adding cached LLM concepts when configured."""
    nodes, edges = extract_graph(chunks)
    provider = build_llm_provider(settings) if provider_allowed(settings, "extraction") else None
    if provider is None:
        for node in nodes:
            node.metadata["extraction_provider"] = "deterministic-local"
        return nodes, edges

    llm_nodes: list[ConceptNode] = []
    llm_edges: list[SemanticEdge] = []
    for chunk in chunks:
        try:
            chunk_graph = extract_chunk_graph(chunk, settings, provider_name=provider.name)
        except Exception as exc:  # pragma: no cover - external provider fallback
            llm_edges.append(
                extraction_warning_edge(chunk, f"LLM extraction fallback for chunk: {exc}")
            )
            continue
        chunk_nodes = nodes_for_llm_chunk(chunk, chunk_graph)
        llm_nodes.extend(chunk_nodes)
        llm_edges.extend(edges_for_llm_chunk(chunk, chunk_graph, chunk_nodes))

    all_nodes = dedupe_nodes([*nodes, *llm_nodes])
    all_edges = dedupe_semantic_edges(
        [edge for edge in [*edges, *llm_edges] if edge.source != edge.target]
    )
    return all_nodes, all_edges


def extract_chunk_graph(chunk: Chunk, settings: Settings, *, provider_name: str) -> LLMChunkGraph:
    """Extract one chunk graph through the configured cached LLM provider."""
    provider = build_llm_provider(settings)
    if provider is None:
        raise ValueError("LLM provider is not configured")
    system = (
        "You extract compact, source-grounded engineering knowledge graphs. "
        "Return only JSON with keys concepts, relations, and warnings. "
        "Use only facts stated in the provided chunk. Valid edge types are related_to, "
        "supports, contradicts, depends_on, caused_by, implements, and portal."
    )
    user = "\n".join(
        [
            f"schema_version: {LLM_EXTRACTION_SCHEMA_VERSION}",
            f"provider: {provider_name}",
            f"title: {chunk.title}",
            f"domain: {chunk.domain}",
            "chunk:",
            chunk.text[:4000],
        ]
    )
    payload = cached_json_completion(
        settings,
        namespace="extract",
        cache_parts=[
            LLM_EXTRACTION_SCHEMA_VERSION,
            provider.name,
            provider.model,
            chunk.id,
            chunk.text,
        ],
        system=system,
        user=user,
        provider=provider,
    )
    return LLMChunkGraph.model_validate(payload)


def nodes_for_llm_chunk(chunk: Chunk, graph: LLMChunkGraph) -> list[ConceptNode]:
    """Convert validated LLM concepts into Tortus graph nodes."""
    nodes: list[ConceptNode] = []
    for concept in graph.concepts:
        label = clean_label(concept.label)
        if not label:
            continue
        nodes.append(
            ConceptNode(
                id=stable_id("llm-concept", chunk.id, label),
                label=label,
                text=concept.summary,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                memberships=[
                    SubgraphMembership(subgraph=chunk.domain, weight=1.0),
                    SubgraphMembership(subgraph=chunk.title.lower().replace(" ", "-"), weight=0.7),
                ],
                evidence=[chunk.evidence],
                confidence=concept.confidence,
                metadata={
                    "terms": important_terms(concept.summary, limit=6),
                    "phrases": noun_phrases(f"{label}. {concept.summary}", limit=6),
                    "source_title": chunk.title,
                    "source_metadata": chunk.metadata,
                    "extraction_provider": "llm",
                    "schema_version": LLM_EXTRACTION_SCHEMA_VERSION,
                },
            )
        )
    return nodes


def edges_for_llm_chunk(
    chunk: Chunk,
    graph: LLMChunkGraph,
    nodes: list[ConceptNode],
) -> list[SemanticEdge]:
    """Convert validated LLM relations into typed Tortus edges."""
    by_label = {node.label.lower(): node for node in nodes}
    edges: list[SemanticEdge] = []
    for relation in graph.relations:
        source = by_label.get(clean_label(relation.source_label).lower())
        target = by_label.get(clean_label(relation.target_label).lower())
        if source is None or target is None or source.id == target.id:
            continue
        edge_type = edge_type_for_llm_value(relation.edge_type)
        edges.append(
            SemanticEdge(
                id=stable_id("llm-edge", chunk.id, source.id, target.id, edge_type.value),
                source=source.id,
                target=target.id,
                edge_type=edge_type,
                weight=min(0.94, 0.52 + relation.confidence * 0.38),
                evidence=[chunk.evidence],
                metadata={
                    "reason": "llm_extracted_relation",
                    "rationale": relation.rationale,
                    "extraction_provider": "llm",
                    "schema_version": LLM_EXTRACTION_SCHEMA_VERSION,
                },
            )
        )
    return edges


def edge_type_for_llm_value(value: str) -> EdgeType:
    """Map an LLM edge-type string into a known EdgeType."""
    normalized = value.strip().lower().replace("-", "_")
    try:
        return EdgeType(normalized)
    except ValueError:
        return EdgeType.RELATED_TO


def clean_label(value: str) -> str:
    """Normalize a concept label without making it opaque."""
    return " ".join(value.strip().split())[:96]


def dedupe_nodes(nodes: list[ConceptNode]) -> list[ConceptNode]:
    """Deduplicate nodes by id while preserving the highest-confidence version."""
    by_id: dict[str, ConceptNode] = {}
    for node in nodes:
        existing = by_id.get(node.id)
        if existing is None or node.confidence > existing.confidence:
            by_id[node.id] = node
    return list(by_id.values())


def dedupe_semantic_edges(edges: list[SemanticEdge]) -> list[SemanticEdge]:
    """Deduplicate semantic edges by id while preserving the strongest edge."""
    by_id: dict[str, SemanticEdge] = {}
    for edge in edges:
        existing = by_id.get(edge.id)
        if existing is None or edge.weight > existing.weight:
            by_id[edge.id] = edge
    return list(by_id.values())


def extraction_warning_edge(chunk: Chunk, warning: str) -> SemanticEdge:
    """Build a harmless self-contained warning edge for extraction diagnostics."""
    node_id = stable_id("extract-warning", chunk.id, warning)
    return SemanticEdge(
        id=stable_id("extract-warning-edge", chunk.id, warning),
        source=node_id,
        target=node_id,
        edge_type=EdgeType.RELATED_TO,
        weight=0.0,
        evidence=[chunk.evidence],
        metadata={
            "reason": "llm_extraction_warning",
            "warning": warning,
        },
    )
