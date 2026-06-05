"""Baseline retrieval strategies for Tortus evaluation."""

import math
import time
from collections import Counter
from hashlib import sha1

from pydantic import BaseModel, Field

from .graph_store import GraphStore
from .models import (
    ConceptNode,
    EdgeType,
    EvidenceSpan,
    ReasoningHop,
    SearchHit,
    SemanticEdge,
    TraversalPolicy,
)
from .sharding import ToroidalShardSimulator
from .text import tokenize
from .torus import torus_distance
from .traversal import QueryEngine, dedupe_evidence, estimate_tokens, synthesize_evidence_answer

STRATEGIES = (
    "tortus_torus",
    "vector_only",
    "bm25",
    "hybrid_dense_bm25",
    "graph_local",
    "community_summary",
    "bounded_agentic",
    "torus_layout",
    "euclidean_layout",
    "random_layout",
)


class StrategyRun(BaseModel):
    """Result payload for one baseline or Tortus strategy run."""

    strategy: str
    hits: list[SearchHit] = Field(default_factory=list)
    evidence: list[EvidenceSpan] = Field(default_factory=list)
    answer: str = ""
    latency_ms: float
    nodes_visited: int
    hops_taken: int
    shard_fanout: int
    tokens_estimated: int
    path_edge_types: list[str] = Field(default_factory=list)
    portal_hops: int = 0
    shard_crossings: int = 0
    warnings: list[str] = Field(default_factory=list)


def run_strategy(
    engine: QueryEngine,
    query: str,
    strategy: str,
    policy: TraversalPolicy,
    top_k: int = 5,
) -> StrategyRun:
    """Dispatch a retrieval strategy by name."""
    if strategy == "tortus_torus":
        return run_tortus(engine, query, policy)
    if strategy == "vector_only":
        return run_vector_only(engine, query, top_k=top_k)
    if strategy == "bm25":
        return run_bm25(engine.graph, query, top_k=top_k)
    if strategy == "hybrid_dense_bm25":
        return run_hybrid_dense_bm25(engine, query, top_k=top_k)
    if strategy == "graph_local":
        return run_tortus(
            engine,
            query,
            policy.model_copy(update={"local_only": True}),
            strategy="graph_local",
        )
    if strategy == "community_summary":
        return run_community_summary(engine, query, top_k=top_k)
    if strategy == "bounded_agentic":
        return run_bounded_agentic(engine, query, policy=policy, top_k=top_k)
    if strategy == "torus_layout":
        return run_layout_probe(engine, query, distance="torus", top_k=top_k)
    if strategy == "euclidean_layout":
        return run_layout_probe(engine, query, distance="euclidean", top_k=top_k)
    if strategy == "random_layout":
        return run_layout_probe(engine, query, distance="random", top_k=top_k)
    raise ValueError(f"unknown strategy: {strategy}")


def run_tortus(
    engine: QueryEngine,
    query: str,
    policy: TraversalPolicy,
    strategy: str = "tortus_torus",
) -> StrategyRun:
    """Run the Tortus graph traversal strategy."""
    started = time.perf_counter()
    result = engine.answer(query, policy=policy)
    latency_ms = (time.perf_counter() - started) * 1000
    domains = domains_for_hops(engine.graph, [hop.from_node for hop in result.reasoning_path])
    domains |= domains_for_hops(engine.graph, [hop.to_node for hop in result.reasoning_path])
    return StrategyRun(
        strategy=strategy,
        hits=[],
        evidence=result.evidence,
        answer=result.answer,
        latency_ms=latency_ms,
        nodes_visited=result.budget.nodes_visited,
        hops_taken=result.budget.hops_taken,
        shard_fanout=result.budget.shard_fanout or max(1, len(domains)),
        portal_hops=result.budget.portal_hops,
        shard_crossings=result.budget.shard_crossings,
        tokens_estimated=result.budget.tokens_estimated,
        path_edge_types=[hop.edge_type.value for hop in result.reasoning_path],
        warnings=result.warnings,
    )


def run_vector_only(engine: QueryEngine, query: str, top_k: int = 5) -> StrategyRun:
    """Run dense retrieval without graph traversal."""
    started = time.perf_counter()
    query_vector = engine.embeddings.embed([query])[0]
    hits = attach_evidence(engine.graph, engine.index.search(query_vector, top_k=top_k))
    evidence = dedupe_evidence([span for hit in hits for span in hit.evidence])
    latency_ms = (time.perf_counter() - started) * 1000
    return StrategyRun(
        strategy="vector_only",
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=latency_ms,
        nodes_visited=len(hits),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(engine.graph, hits),
        tokens_estimated=estimate_tokens(query, evidence),
    )


def run_bm25(graph: GraphStore, query: str, top_k: int = 5) -> StrategyRun:
    """Run a lexical BM25 baseline over concept nodes."""
    started = time.perf_counter()
    nodes = graph.list_nodes()
    query_terms = tokenize(query)
    scored = score_bm25(nodes, query_terms)
    hits = [
        SearchHit(node_id=node.id, label=node.label, score=score, evidence=node.evidence)
        for node, score in scored[:top_k]
        if score > 0
    ]
    evidence = dedupe_evidence([span for hit in hits for span in hit.evidence])
    latency_ms = (time.perf_counter() - started) * 1000
    return StrategyRun(
        strategy="bm25",
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=latency_ms,
        nodes_visited=len(hits),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(graph, hits),
        tokens_estimated=estimate_tokens(query, evidence),
        warnings=[] if hits else ["BM25 found no lexical matches."],
    )


def run_hybrid_dense_bm25(engine: QueryEngine, query: str, top_k: int = 5) -> StrategyRun:
    """Run a weighted dense plus BM25 hybrid retrieval baseline."""
    started = time.perf_counter()
    nodes = engine.graph.list_nodes()
    query_vector = engine.embeddings.embed([query])[0]
    dense_hits = attach_evidence(engine.graph, engine.index.search(query_vector, top_k=len(nodes)))
    dense_scores = normalize_scores({hit.node_id: hit.score for hit in dense_hits})
    bm25_scores = normalize_scores(
        {node.id: score for node, score in score_bm25(nodes, tokenize(query))}
    )
    ranked = sorted(
        nodes,
        key=lambda node: (
            (0.58 * dense_scores.get(node.id, 0.0)) + (0.42 * bm25_scores.get(node.id, 0.0))
        ),
        reverse=True,
    )
    hits = [
        SearchHit(
            node_id=node.id,
            label=node.label,
            score=(0.58 * dense_scores.get(node.id, 0.0)) + (0.42 * bm25_scores.get(node.id, 0.0)),
            evidence=node.evidence,
        )
        for node in ranked[:top_k]
    ]
    evidence = dedupe_evidence([span for hit in hits for span in hit.evidence])
    return StrategyRun(
        strategy="hybrid_dense_bm25",
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=len(hits),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(engine.graph, hits),
        tokens_estimated=estimate_tokens(query, evidence),
    )


def run_community_summary(engine: QueryEngine, query: str, top_k: int = 5) -> StrategyRun:
    """Run a local community-summary-style retrieval approximation."""
    started = time.perf_counter()
    nodes = engine.graph.list_nodes()
    query_terms = tokenize(query)
    grouped = group_nodes_by_domain(nodes)
    community_scores: list[tuple[str, float, list[ConceptNode]]] = []
    for domain, domain_nodes in grouped.items():
        text = " ".join(node.label + " " + node.text for node in domain_nodes)
        lexical_overlap = len(set(query_terms).intersection(tokenize(text)))
        edge_density = len(domain_nodes) / max(1, len(nodes))
        community_scores.append((domain, lexical_overlap + edge_density, domain_nodes))
    community_scores.sort(key=lambda item: item[1], reverse=True)

    selected_nodes: list[ConceptNode] = []
    for _, _, domain_nodes in community_scores[:2]:
        ranked = score_bm25(domain_nodes, query_terms)
        selected_nodes.extend(node for node, score in ranked[:top_k] if score > 0)
    deduped_nodes = dedupe_nodes(selected_nodes)[:top_k]
    hits = [
        SearchHit(node_id=node.id, label=node.label, score=1.0, evidence=node.evidence)
        for node in deduped_nodes
    ]
    evidence = dedupe_evidence([span for hit in hits for span in hit.evidence])
    return StrategyRun(
        strategy="community_summary",
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=len(deduped_nodes),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(engine.graph, hits),
        tokens_estimated=estimate_tokens(query, evidence),
        warnings=[] if evidence else ["Community summary baseline found no supporting community."],
    )


def run_bounded_agentic(
    engine: QueryEngine,
    query: str,
    policy: TraversalPolicy,
    top_k: int = 5,
) -> StrategyRun:
    """Run a deterministic bounded-agentic search approximation."""
    started = time.perf_counter()
    query_vector = engine.embeddings.embed([query])[0]
    dense_hits = engine.index.search(query_vector, top_k=2)
    bm25_hits = [
        SearchHit(node_id=node.id, label=node.label, score=score, evidence=node.evidence)
        for node, score in score_bm25(engine.graph.list_nodes(), tokenize(query))[:2]
        if score > 0
    ]
    seed_ids = [hit.node_id for hit in dense_hits] + [hit.node_id for hit in bm25_hits]
    frontier: list[tuple[str, float, int]] = [
        (node_id, 1.0 - (index * 0.05), 0) for index, node_id in enumerate(dict.fromkeys(seed_ids))
    ]
    visited: set[str] = set()
    evidence: list[EvidenceSpan] = []
    hops: list[ReasoningHop] = []
    portal_hops = 0

    while frontier and len(visited) < min(policy.max_nodes, 18):
        if (time.perf_counter() - started) * 1000 > policy.max_ms:
            break
        node_id, score, depth = frontier.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)
        node = engine.graph.get_node(node_id)
        if node is None:
            continue
        evidence.extend(node.evidence)
        if depth >= min(policy.max_hops, 2):
            continue
        for edge in sorted(
            engine.graph.neighbors(node_id),
            key=lambda item: lexical_edge_score(engine.graph, item, node_id, query),
            reverse=True,
        )[:3]:
            if edge.edge_type == EdgeType.PORTAL and portal_hops >= min(policy.max_portal_hops, 3):
                continue
            target = edge.target if edge.source == node_id else edge.source
            if target in visited:
                continue
            if edge.edge_type == EdgeType.PORTAL:
                portal_hops += 1
            frontier.append((target, score * 0.75 + edge.weight, depth + 1))
            hops.append(
                ReasoningHop.model_validate(
                    {
                        "from": node_id,
                        "to": target,
                        "edge_type": edge.edge_type,
                        "weight": edge.weight,
                        "evidence": edge.evidence[:1],
                    }
                )
            )
        frontier.sort(key=lambda item: item[1], reverse=True)

    nodes = engine.graph.list_nodes()
    visited_hits = [
        SearchHit(node_id=node.id, label=node.label, score=1.0, evidence=node.evidence)
        for node in nodes
        if node.id in visited
    ][:top_k]
    evidence = dedupe_evidence(evidence)
    shard_simulator = ToroidalShardSimulator()
    return StrategyRun(
        strategy="bounded_agentic",
        hits=visited_hits,
        evidence=evidence[:10],
        answer=synthesize_evidence_answer(query, visited_hits, evidence).answer,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=len(visited),
        hops_taken=len(hops),
        portal_hops=portal_hops,
        shard_fanout=shard_simulator.fanout_for_node_ids(list(visited), nodes),
        shard_crossings=shard_simulator.crossing_count(hops, nodes),
        tokens_estimated=estimate_tokens(query, evidence),
        path_edge_types=[hop.edge_type.value for hop in hops],
        warnings=[] if len(visited) < 18 else ["Bounded agentic baseline reached tool budget."],
    )


def run_layout_probe(
    engine: QueryEngine,
    query: str,
    distance: str,
    top_k: int = 5,
) -> StrategyRun:
    """Run a layout-distance retrieval probe."""
    started = time.perf_counter()
    query_vector = engine.embeddings.embed([query])[0]
    seed_hits = engine.index.search(query_vector, top_k=1)
    if not seed_hits:
        return StrategyRun(
            strategy=f"{distance}_layout",
            latency_ms=(time.perf_counter() - started) * 1000,
            nodes_visited=0,
            hops_taken=0,
            shard_fanout=0,
            tokens_estimated=estimate_tokens(query, []),
            warnings=["No vector seed was available for layout probe."],
        )
    seed = engine.graph.get_node(seed_hits[0].node_id)
    nodes = engine.graph.list_nodes()
    ranked = rank_by_layout(query, seed, nodes, distance)
    hits = [
        SearchHit(node_id=node.id, label=node.label, score=score, evidence=node.evidence)
        for node, score in ranked[:top_k]
    ]
    evidence = dedupe_evidence([span for hit in hits for span in hit.evidence])
    return StrategyRun(
        strategy=f"{distance}_layout",
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=len(hits),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(engine.graph, hits),
        tokens_estimated=estimate_tokens(query, evidence),
    )


def rank_by_layout(
    query: str,
    seed: ConceptNode | None,
    nodes: list[ConceptNode],
    distance: str,
) -> list[tuple[ConceptNode, float]]:
    """Return rank by layout."""
    if seed is None or seed.torus is None:
        return []
    scored: list[tuple[ConceptNode, float]] = []
    for node in nodes:
        if node.torus is None:
            continue
        if distance == "torus":
            score = -torus_distance(seed.torus, node.torus)
        elif distance == "euclidean":
            delta_theta = seed.torus.theta - node.torus.theta
            delta_phi = seed.torus.phi - node.torus.phi
            score = -math.sqrt(delta_theta * delta_theta + delta_phi * delta_phi)
        elif distance == "random":
            digest = sha1(f"{query}:{node.id}".encode()).hexdigest()
            score = int(digest[:8], 16) / 0xFFFFFFFF
        else:
            raise ValueError(f"unknown layout distance: {distance}")
        scored.append((node, score))
    return sorted(scored, key=lambda item: item[1], reverse=True)


def score_bm25(nodes: list[ConceptNode], query_terms: list[str]) -> list[tuple[ConceptNode, float]]:
    """Score concept nodes with a compact BM25 implementation."""
    if not nodes:
        return []
    documents = [tokenize(node.label + " " + node.text) for node in nodes]
    doc_lengths = [len(document) for document in documents]
    avg_doc_length = sum(doc_lengths) / len(doc_lengths)
    document_frequency = Counter(term for document in documents for term in set(document))
    total_docs = len(nodes)
    k1 = 1.5
    b = 0.75
    scored: list[tuple[ConceptNode, float]] = []
    for node, terms, doc_length in zip(nodes, documents, doc_lengths, strict=True):
        term_counts = Counter(terms)
        score = 0.0
        for term in query_terms:
            if term not in term_counts:
                continue
            df = document_frequency[term]
            idf = math.log(1 + (total_docs - df + 0.5) / (df + 0.5))
            frequency = term_counts[term]
            denominator = frequency + k1 * (1 - b + b * doc_length / avg_doc_length)
            score += idf * (frequency * (k1 + 1)) / denominator
        scored.append((node, score))
    return sorted(scored, key=lambda item: item[1], reverse=True)


def attach_evidence(graph: GraphStore, hits: list[SearchHit]) -> list[SearchHit]:
    """Attach attach evidence."""
    attached: list[SearchHit] = []
    for hit in hits:
        node = graph.get_node(hit.node_id)
        attached.append(hit.model_copy(update={"evidence": node.evidence if node else []}))
    return attached


def domains_for_hits(graph: GraphStore, hits: list[SearchHit]) -> set[str]:
    """Return domains for hits."""
    return domains_for_hops(graph, [hit.node_id for hit in hits])


def shard_fanout_for_hits(graph: GraphStore, hits: list[SearchHit]) -> int:
    """Return shard fanout for hits."""
    nodes = graph.list_nodes()
    hit_ids = [hit.node_id for hit in hits]
    return ToroidalShardSimulator().fanout_for_node_ids(hit_ids, nodes)


def domains_for_hops(graph: GraphStore, node_ids: list[str]) -> set[str]:
    """Return domains for hops."""
    domains: set[str] = set()
    for node_id in node_ids:
        node = graph.get_node(node_id)
        if node and node.memberships:
            domains.add(node.memberships[0].subgraph)
    return domains


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """Normalize arbitrary scores into the [0, 1] range."""
    if not scores:
        return {}
    minimum = min(scores.values())
    maximum = max(scores.values())
    if maximum == minimum:
        return {key: 1.0 for key in scores}
    return {key: (value - minimum) / (maximum - minimum) for key, value in scores.items()}


def group_nodes_by_domain(nodes: list[ConceptNode]) -> dict[str, list[ConceptNode]]:
    """Group concept nodes by their primary domain membership."""
    grouped: dict[str, list[ConceptNode]] = {}
    for node in nodes:
        domain = node.memberships[0].subgraph if node.memberships else "unknown"
        grouped.setdefault(domain, []).append(node)
    return grouped


def dedupe_nodes(nodes: list[ConceptNode]) -> list[ConceptNode]:
    """Deduplicate nodes while preserving rank order."""
    seen: set[str] = set()
    deduped: list[ConceptNode] = []
    for node in nodes:
        if node.id in seen:
            continue
        seen.add(node.id)
        deduped.append(node)
    return deduped


def lexical_edge_score(
    graph: GraphStore,
    edge: SemanticEdge,
    current_node_id: str,
    query: str,
) -> float:
    """Score lexical edge score."""
    target_id = edge.target if edge.source == current_node_id else edge.source
    target = graph.get_node(target_id)
    if target is None:
        return 0.0
    overlap = len(set(tokenize(query)).intersection(tokenize(target.label + " " + target.text)))
    edge_type_bonus = 0.20 if edge.edge_type == EdgeType.PORTAL else 0.05
    return float(edge.weight) + edge_type_bonus + overlap
