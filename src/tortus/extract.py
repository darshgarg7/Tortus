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


def extract_graph(
    chunks: list[Chunk],
    *,
    max_edges_per_phrase: int | None = None,
) -> tuple[list[ConceptNode], list[SemanticEdge]]:
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
        for left, right in iter_phrase_pairs(
            phrase_nodes,
            max_edges_per_phrase=max_edges_per_phrase,
        ):
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


def iter_phrase_pairs(
    phrase_nodes: list[ConceptNode],
    *,
    max_edges_per_phrase: int | None = None,
) -> list[tuple[ConceptNode, ConceptNode]]:
    """Return deterministic node pairs for a shared phrase, optionally capped."""
    if max_edges_per_phrase is not None and max_edges_per_phrase <= 0:
        return []

    pair_count = len(phrase_nodes) * (len(phrase_nodes) - 1) // 2
    if max_edges_per_phrase is None or pair_count <= max_edges_per_phrase:
        return [
            (left, right)
            for idx, left in enumerate(phrase_nodes)
            for right in phrase_nodes[idx + 1 :]
        ]

    pairs: list[tuple[ConceptNode, ConceptNode]] = []
    seen: set[tuple[str, str]] = set()

    def add_pair(left: ConceptNode, right: ConceptNode) -> None:
        if len(pairs) >= max_edges_per_phrase or left.id == right.id:
            return
        key = (
            min(left.id, right.id),
            max(left.id, right.id),
        )
        if key in seen:
            return
        seen.add(key)
        pairs.append((left, right))

    local_budget = max(1, max_edges_per_phrase // 2)
    stride = max(1, (len(phrase_nodes) - 1) // local_budget)
    for idx in range(0, len(phrase_nodes) - 1, stride):
        add_pair(phrase_nodes[idx], phrase_nodes[idx + 1])
        if len(pairs) >= local_budget:
            break

    by_domain: dict[str, list[ConceptNode]] = defaultdict(list)
    for node in phrase_nodes:
        by_domain[node.memberships[0].subgraph].append(node)
    domains = sorted(by_domain)
    domain_pairs = [
        (left_domain, right_domain)
        for idx, left_domain in enumerate(domains)
        for right_domain in domains[idx + 1 :]
    ]
    max_domain_size = max((len(nodes) for nodes in by_domain.values()), default=0)
    for ordinal in range(max_domain_size):
        for left_domain, right_domain in domain_pairs:
            left_group = by_domain[left_domain]
            right_group = by_domain[right_domain]
            add_pair(
                left_group[ordinal % len(left_group)],
                right_group[ordinal % len(right_group)],
            )
            if len(pairs) >= max_edges_per_phrase:
                return pairs

    offset = 2
    while len(pairs) < max_edges_per_phrase and offset < len(phrase_nodes):
        for idx in range(0, len(phrase_nodes) - offset, stride):
            add_pair(phrase_nodes[idx], phrase_nodes[idx + offset])
            if len(pairs) >= max_edges_per_phrase:
                return pairs
        offset += 1
    return pairs


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
