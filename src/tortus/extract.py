"""Deterministic concept and edge extraction."""

import hashlib
import re
from collections import defaultdict

from .models import (
    Chunk,
    ConceptNode,
    EdgeType,
    SemanticEdge,
    SubgraphMembership,
)

TOKEN_RE = re.compile(r"[a-z][a-z0-9-]{2,}")
STOPWORDS = {
    "and",
    "are",
    "because",
    "from",
    "have",
    "into",
    "that",
    "the",
    "this",
    "with",
    "while",
}


def important_terms(text: str, limit: int = 8) -> list[str]:
    """Return important terms."""
    counts: dict[str, int] = defaultdict(int)
    for token in TOKEN_RE.findall(text.lower()):
        if token not in STOPWORDS:
            counts[token] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ranked[:limit]]


def stable_id(prefix: str, *parts: str) -> str:
    """Return stable id."""
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{digest}"


def extract_graph(chunks: list[Chunk]) -> tuple[list[ConceptNode], list[SemanticEdge]]:
    """Extract extract graph."""
    nodes: list[ConceptNode] = []
    for chunk in chunks:
        terms = important_terms(chunk.text, limit=5)
        label = " / ".join(terms[:3]) if terms else chunk.title
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
                )
            )

    term_to_nodes: dict[str, list[ConceptNode]] = defaultdict(list)
    for node in nodes:
        for term in important_terms(node.text, limit=8):
            term_to_nodes[term].append(node)
    for term, term_nodes in term_to_nodes.items():
        for idx, left in enumerate(term_nodes):
            for right in term_nodes[idx + 1 :]:
                if left.id == right.id:
                    continue
                left_domain = left.memberships[0].subgraph
                right_domain = right.memberships[0].subgraph
                edge_type = EdgeType.PORTAL if left_domain != right_domain else EdgeType.RELATED_TO
                weight = 0.78 if edge_type == EdgeType.PORTAL else 0.56
                edges.append(
                    SemanticEdge(
                        id=stable_id("edge", left.id, right.id, term, edge_type),
                        source=left.id,
                        target=right.id,
                        edge_type=edge_type,
                        weight=weight,
                        evidence=left.evidence + right.evidence,
                        metadata={"shared_term": term},
                    )
                )
    return nodes, dedupe_edges(edges)


def dedupe_edges(edges: list[SemanticEdge]) -> list[SemanticEdge]:
    """Deduplicate dedupe edges."""
    seen: set[str] = set()
    unique: list[SemanticEdge] = []
    for edge in edges:
        if edge.id not in seen:
            seen.add(edge.id)
            unique.append(edge)
    return unique
