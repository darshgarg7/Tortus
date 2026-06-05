"""Deterministic source-aware concept and edge extraction."""

import hashlib
from collections import defaultdict

from .models import (
    Chunk,
    ConceptNode,
    EdgeType,
    SemanticEdge,
    SubgraphMembership,
)
from .text import important_terms, noun_phrases, token_set


def stable_id(prefix: str, *parts: str) -> str:
    """Return stable id."""
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


def extract_graph(chunks: list[Chunk]) -> tuple[list[ConceptNode], list[SemanticEdge]]:
    """Extract a deterministic concept graph from chunked source documents."""
    nodes: list[ConceptNode] = []
    for chunk in chunks:
        terms = important_terms(chunk.text, limit=5)
        phrases = noun_phrases(chunk.text, limit=5)
        label = phrases[0] if phrases else (" / ".join(terms[:3]) if terms else chunk.title)
        nodes.append(
            ConceptNode(
                id=stable_id("concept", chunk.id, label),
                label=label,
                text=chunk.text,
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                memberships=[
                    SubgraphMembership(subgraph=chunk.domain, weight=1.0),
                    SubgraphMembership(subgraph=chunk.title.lower().replace(" ", "-"), weight=0.65),
                ],
                evidence=[chunk.evidence],
                confidence=0.72,
                metadata={
                    "terms": terms,
                    "phrases": phrases,
                    "source_title": chunk.title,
                    "source_metadata": chunk.metadata,
                },
            )
        )

    edges: list[SemanticEdge] = []
    by_doc: dict[str, list[ConceptNode]] = defaultdict(list)
    for node in nodes:
        by_doc[node.document_id].append(node)
    for doc_nodes in by_doc.values():
        doc_nodes.sort(key=lambda node: node.chunk_id)
        for left, right in zip(doc_nodes, doc_nodes[1:], strict=False):
            edges.append(
                SemanticEdge(
                    id=stable_id("edge", left.id, right.id, EdgeType.ADJACENT_TO),
                    source=left.id,
                    target=right.id,
                    edge_type=EdgeType.ADJACENT_TO,
                    weight=0.62,
                    evidence=left.evidence + right.evidence,
                    metadata={"reason": "same_document_adjacency"},
                )
            )

    phrase_to_nodes: dict[str, list[ConceptNode]] = defaultdict(list)
    for node in nodes:
        phrases = [str(item) for item in node.metadata.get("phrases", [])]
        terms = [str(item) for item in node.metadata.get("terms", [])]
        for phrase in phrases + terms[:6]:
            phrase_to_nodes[phrase].append(node)
    for phrase, phrase_nodes in phrase_to_nodes.items():
        for idx, left in enumerate(phrase_nodes):
            for right in phrase_nodes[idx + 1 :]:
                if left.id == right.id:
                    continue
                left_domain = left.memberships[0].subgraph
                right_domain = right.memberships[0].subgraph
                edge_type = EdgeType.PORTAL if left_domain != right_domain else EdgeType.RELATED_TO
                if "requires" in left.text.lower() or "requires" in right.text.lower():
                    edge_type = EdgeType.DEPENDS_ON if edge_type != EdgeType.PORTAL else edge_type
                elif "resolution" in left.text.lower() or "resolution" in right.text.lower():
                    edge_type = EdgeType.SUPPORTS if edge_type != EdgeType.PORTAL else edge_type
                shared_terms = sorted(token_set(left.text).intersection(token_set(right.text)))
                weight = edge_weight(edge_type, len(shared_terms), phrase)
                edges.append(
                    SemanticEdge(
                        id=stable_id("edge", left.id, right.id, phrase, edge_type),
                        source=left.id,
                        target=right.id,
                        edge_type=edge_type,
                        weight=weight,
                        evidence=left.evidence + right.evidence,
                        metadata={
                            "shared_phrase": phrase,
                            "shared_terms": shared_terms[:8],
                            "reason": "shared_phrase_or_term",
                        },
                    )
                )
    return nodes, dedupe_edges(edges)


def edge_weight(edge_type: EdgeType, shared_count: int, phrase: str) -> float:
    """Score a deterministic edge from type, overlap, and phrase specificity."""
    base = {
        EdgeType.PORTAL: 0.66,
        EdgeType.SUPPORTS: 0.64,
        EdgeType.DEPENDS_ON: 0.62,
        EdgeType.RELATED_TO: 0.52,
        EdgeType.ADJACENT_TO: 0.58,
    }.get(edge_type, 0.50)
    specificity = min(0.12, len(phrase.split()) * 0.03)
    overlap = min(0.14, shared_count * 0.02)
    return min(0.92, base + specificity + overlap)


def dedupe_edges(edges: list[SemanticEdge]) -> list[SemanticEdge]:
    """Deduplicate edges while keeping the strongest version of repeated links."""
    seen: set[str] = set()
    unique: list[SemanticEdge] = []
    for edge in sorted(edges, key=lambda item: item.weight, reverse=True):
        if edge.id not in seen:
            seen.add(edge.id)
            unique.append(edge)
    return unique
