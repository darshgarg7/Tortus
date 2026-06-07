"""Baseline retrieval strategies for Tortus evaluation."""

import json
import math
import os
import shlex
import subprocess
import time
from collections import Counter
from hashlib import sha1
from importlib import metadata, util
from typing import Any, cast

from pydantic import BaseModel, Field, PrivateAttr

from .embeddings import EmbeddingProvider
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

LOCAL_STRATEGIES = (
    "tortus_torus",
    "vector_only_local",
    "bm25_local",
    "hybrid_dense_bm25_local",
    "hybrid_graph_rerank_local",
    "graph_local",
    "community_summary_local",
    "bounded_agentic_local",
    "torus_layout_local",
    "euclidean_layout_local",
    "random_layout_local",
)
EXTERNAL_STRATEGIES = ("graphrag_external", "llamaindex_external", "lightrag_external")
STRATEGIES = LOCAL_STRATEGIES
ALL_STRATEGIES = LOCAL_STRATEGIES + EXTERNAL_STRATEGIES
STRATEGY_ALIASES = {
    "vector_only": "vector_only_local",
    "bm25": "bm25_local",
    "hybrid_dense_bm25": "hybrid_dense_bm25_local",
    "hybrid_graph_rerank": "hybrid_graph_rerank_local",
    "community_summary": "community_summary_local",
    "bounded_agentic": "bounded_agentic_local",
    "torus_layout": "torus_layout_local",
    "euclidean_layout": "euclidean_layout_local",
    "random_layout": "random_layout_local",
}


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
    external: bool = False
    skipped: bool = False
    metadata: dict[str, str] = Field(default_factory=dict)


def run_strategy(
    engine: QueryEngine,
    query: str,
    strategy: str,
    policy: TraversalPolicy,
    top_k: int = 5,
) -> StrategyRun:
    """Dispatch a retrieval strategy by name."""
    strategy = STRATEGY_ALIASES.get(strategy, strategy)
    if strategy == "tortus_torus":
        return run_tortus(engine, query, policy)
    if strategy == "vector_only_local":
        return run_vector_only(engine, query, top_k=top_k, strategy=strategy)
    if strategy == "bm25_local":
        return run_bm25(engine.graph, query, top_k=top_k, strategy=strategy)
    if strategy == "hybrid_dense_bm25_local":
        return run_hybrid_dense_bm25(engine, query, top_k=top_k, strategy=strategy)
    if strategy == "hybrid_graph_rerank_local":
        return run_hybrid_graph_rerank(engine, query, top_k=top_k, strategy=strategy)
    if strategy == "graph_local":
        return run_tortus(
            engine,
            query,
            policy.model_copy(update={"local_only": True}),
            strategy="graph_local",
        )
    if strategy == "community_summary_local":
        return run_community_summary(engine, query, top_k=top_k, strategy=strategy)
    if strategy == "bounded_agentic_local":
        return run_bounded_agentic(engine, query, policy=policy, top_k=top_k, strategy=strategy)
    if strategy == "torus_layout_local":
        return run_layout_probe(engine, query, distance="torus", top_k=top_k, strategy=strategy)
    if strategy == "euclidean_layout_local":
        return run_layout_probe(engine, query, distance="euclidean", top_k=top_k, strategy=strategy)
    if strategy == "random_layout_local":
        return run_layout_probe(engine, query, distance="random", top_k=top_k, strategy=strategy)
    if strategy == "llamaindex_external":
        return run_llamaindex_external(engine, query, policy=policy, top_k=top_k)
    if strategy in EXTERNAL_STRATEGIES:
        return run_external_command_baseline(strategy, query, policy=policy)
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


def run_vector_only(
    engine: QueryEngine,
    query: str,
    top_k: int = 5,
    strategy: str = "vector_only_local",
) -> StrategyRun:
    """Run dense retrieval without graph traversal."""
    started = time.perf_counter()
    query_vector = engine.embeddings.embed([query])[0]
    hits = attach_evidence(engine.graph, engine.index.search(query_vector, top_k=top_k))
    evidence = dedupe_evidence([span for hit in hits for span in hit.evidence])
    latency_ms = (time.perf_counter() - started) * 1000
    return StrategyRun(
        strategy=strategy,
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=latency_ms,
        nodes_visited=len(hits),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(engine.graph, hits),
        tokens_estimated=estimate_tokens(query, evidence),
    )


def run_bm25(
    graph: GraphStore,
    query: str,
    top_k: int = 5,
    strategy: str = "bm25_local",
) -> StrategyRun:
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
        strategy=strategy,
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


def run_hybrid_dense_bm25(
    engine: QueryEngine,
    query: str,
    top_k: int = 5,
    strategy: str = "hybrid_dense_bm25_local",
) -> StrategyRun:
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
        strategy=strategy,
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=len(hits),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(engine.graph, hits),
        tokens_estimated=estimate_tokens(query, evidence),
    )


def run_hybrid_graph_rerank(
    engine: QueryEngine,
    query: str,
    top_k: int = 5,
    strategy: str = "hybrid_graph_rerank_local",
) -> StrategyRun:
    """Run a stronger hybrid baseline with one-hop graph expansion and reranking."""
    started = time.perf_counter()
    nodes = engine.graph.list_nodes()
    nodes_by_id = {node.id: node for node in nodes}
    query_terms = tokenize(query)
    query_vector = engine.embeddings.embed([query])[0]
    dense_hits = attach_evidence(
        engine.graph,
        engine.index.search(query_vector, top_k=min(12, len(nodes))),
    )
    bm25_ranked = score_bm25(nodes, query_terms)
    dense_scores = normalize_scores({hit.node_id: hit.score for hit in dense_hits})
    bm25_scores = normalize_scores({node.id: score for node, score in bm25_ranked})
    seed_ids = list(
        dict.fromkeys(
            [hit.node_id for hit in dense_hits[:8]]
            + [node.id for node, score in bm25_ranked[:8] if score > 0]
        )
    )
    candidate_scores: dict[str, float] = {}
    hops: list[ReasoningHop] = []
    for seed_id in seed_ids:
        node = nodes_by_id.get(seed_id)
        if node is None:
            continue
        candidate_scores[seed_id] = max(
            candidate_scores.get(seed_id, 0.0),
            rerank_node_score(node, query_terms, dense_scores, bm25_scores),
        )
        for edge in sorted(
            engine.graph.neighbors(seed_id),
            key=lambda item: lexical_edge_score(engine.graph, item, seed_id, query),
            reverse=True,
        )[:4]:
            target_id = edge.target if edge.source == seed_id else edge.source
            target = nodes_by_id.get(target_id)
            if target is None:
                continue
            edge_bonus = 0.18 if edge.edge_type == EdgeType.PORTAL else 0.10
            candidate_scores[target_id] = max(
                candidate_scores.get(target_id, 0.0),
                rerank_node_score(target, query_terms, dense_scores, bm25_scores)
                + edge.weight * 0.10
                + edge_bonus,
            )
            hops.append(
                ReasoningHop.model_validate(
                    {
                        "from": seed_id,
                        "to": target_id,
                        "edge_type": edge.edge_type,
                        "weight": edge.weight,
                        "evidence": edge.evidence[:1],
                    }
                )
            )
    ranked_ids = sorted(
        candidate_scores,
        key=lambda node_id: candidate_scores[node_id],
        reverse=True,
    )
    selected_nodes = [
        nodes_by_id[node_id] for node_id in ranked_ids[:top_k] if node_id in nodes_by_id
    ]
    hits = [
        SearchHit(
            node_id=node.id,
            label=node.label,
            score=candidate_scores.get(node.id, 0.0),
            evidence=node.evidence,
        )
        for node in selected_nodes
    ]
    selected_ids = {node.id for node in selected_nodes}
    selected_hops = [
        hop for hop in hops if hop.to_node in selected_ids or hop.from_node in selected_ids
    ]
    evidence = dedupe_evidence([span for hit in hits for span in hit.evidence])
    shard_simulator = ToroidalShardSimulator()
    return StrategyRun(
        strategy=strategy,
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=len(candidate_scores),
        hops_taken=len(selected_hops),
        portal_hops=sum(hop.edge_type == EdgeType.PORTAL for hop in selected_hops),
        shard_fanout=shard_simulator.fanout_for_node_ids(list(candidate_scores), nodes),
        shard_crossings=shard_simulator.crossing_count(selected_hops, nodes),
        tokens_estimated=estimate_tokens(query, evidence),
        path_edge_types=[hop.edge_type.value for hop in selected_hops],
        warnings=[] if evidence else ["Hybrid graph rerank baseline found no evidence."],
    )


def run_community_summary(
    engine: QueryEngine,
    query: str,
    top_k: int = 5,
    strategy: str = "community_summary_local",
) -> StrategyRun:
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
        strategy=strategy,
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
    strategy: str = "bounded_agentic_local",
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
        strategy=strategy,
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
    strategy: str | None = None,
) -> StrategyRun:
    """Run a layout-distance retrieval probe."""
    started = time.perf_counter()
    query_vector = engine.embeddings.embed([query])[0]
    seed_hits = engine.index.search(query_vector, top_k=1)
    if not seed_hits:
        return StrategyRun(
            strategy=strategy or f"{distance}_layout_local",
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
        strategy=strategy or f"{distance}_layout_local",
        hits=hits,
        evidence=evidence,
        answer=synthesize_evidence_answer(query, hits, evidence).answer,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=len(hits),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(engine.graph, hits),
        tokens_estimated=estimate_tokens(query, evidence),
    )


EXTERNAL_COMMANDS = {
    "graphrag_external": ("microsoft-graphrag", "TORTUS_GRAPHRAG_COMMAND", "graphrag"),
    "llamaindex_external": ("llamaindex", "TORTUS_LLAMA_INDEX_COMMAND", "llama_index"),
    "lightrag_external": ("lightrag", "TORTUS_LIGHTRAG_COMMAND", "lightrag"),
}


def run_llamaindex_external(
    engine: QueryEngine,
    query: str,
    policy: TraversalPolicy,
    top_k: int = 5,
) -> StrategyRun:
    """Run a real LlamaIndex Core retriever baseline over Tortus evidence spans."""
    started = time.perf_counter()
    metadata_payload = {
        "adapter": "llamaindex-core",
        "embedding_provider": type(engine.embeddings).__name__,
    }
    try:
        if util.find_spec("llama_index.core") is None:
            return run_external_command_baseline(
                "llamaindex_external",
                query,
                policy=policy,
            )
        metadata_payload["dependency_version"] = metadata.version("llama-index-core")
        from llama_index.core import VectorStoreIndex
        from llama_index.core.embeddings import BaseEmbedding
        from llama_index.core.schema import TextNode
        from llama_index.core.settings import Settings as LlamaSettings
    except Exception as exc:
        command_template = os.environ.get("TORTUS_LLAMA_INDEX_COMMAND", "")
        if command_template:
            return run_external_command_baseline(
                "llamaindex_external",
                query,
                policy=policy,
            )
        return skipped_external_result(
            "llamaindex_external",
            query,
            started,
            f"llamaindex external baseline skipped: {exc}",
            metadata_payload,
        )

    class TortusLlamaIndexEmbedding(BaseEmbedding):
        """LlamaIndex embedding wrapper backed by the configured Tortus provider."""

        _provider: EmbeddingProvider = PrivateAttr()

        def __init__(self, provider: EmbeddingProvider) -> None:
            super().__init__(model_name=type(provider).__name__)
            self._provider = provider

        def _get_text_embedding(self, text: str) -> list[float]:
            return cast(list[float], self._provider.embed([text])[0].astype(float).tolist())

        def _get_query_embedding(self, query: str) -> list[float]:
            return cast(list[float], self._provider.embed([query])[0].astype(float).tolist())

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return self._get_query_embedding(query)

    nodes: list[Any] = []
    for node in engine.graph.list_nodes():
        for evidence_index, span in enumerate(node.evidence):
            text = span.text.strip() or node.text
            if not text:
                continue
            nodes.append(
                TextNode(
                    text=f"{node.label}\n{text}",
                    id_=f"{node.id}:evidence:{evidence_index}",
                    metadata={
                        "node_id": node.id,
                        "label": node.label,
                        "uri": span.uri,
                        "start": span.start,
                        "end": span.end,
                        "text": span.text,
                    },
                )
            )
    if not nodes:
        return skipped_external_result(
            "llamaindex_external",
            query,
            started,
            "llamaindex external baseline skipped: no evidence spans were available.",
            metadata_payload,
        )

    embed_model = TortusLlamaIndexEmbedding(engine.embeddings)
    LlamaSettings.llm = None
    LlamaSettings.embed_model = embed_model
    index = VectorStoreIndex(nodes, embed_model=embed_model)
    retrieved = index.as_retriever(similarity_top_k=top_k).retrieve(query)
    evidence: list[EvidenceSpan] = []
    hits: list[SearchHit] = []
    for item in retrieved:
        item_node = item.node
        item_metadata = item_node.metadata
        span = EvidenceSpan(
            uri=str(item_metadata.get("uri", "")),
            start=int(item_metadata.get("start", 0)),
            end=int(item_metadata.get("end", 0)),
            text=str(item_metadata.get("text", getattr(item_node, "text", ""))),
        )
        evidence.append(span)
        hits.append(
            SearchHit(
                node_id=str(item_metadata.get("node_id", item_node.node_id)),
                label=str(item_metadata.get("label", item_node.node_id)),
                score=float(item.score or 0.0),
                evidence=[span],
            )
        )
    deduped = dedupe_evidence(evidence)
    return StrategyRun(
        strategy="llamaindex_external",
        hits=hits,
        evidence=deduped,
        answer=synthesize_evidence_answer(query, hits, deduped).answer,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=len(retrieved),
        hops_taken=0,
        shard_fanout=shard_fanout_for_hits(engine.graph, hits),
        tokens_estimated=estimate_tokens(query, deduped),
        warnings=[] if deduped else ["LlamaIndex retriever returned no evidence."],
        external=True,
        skipped=False,
        metadata=metadata_payload,
    )


def skipped_external_result(
    strategy: str,
    query: str,
    started: float,
    warning: str,
    metadata_payload: dict[str, str],
) -> StrategyRun:
    """Return a consistent skipped external baseline payload."""
    return StrategyRun(
        strategy=strategy,
        answer="",
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=0,
        hops_taken=0,
        shard_fanout=0,
        tokens_estimated=estimate_tokens(query, []),
        warnings=[warning],
        external=True,
        skipped=True,
        metadata=metadata_payload,
    )


def run_external_command_baseline(
    strategy: str,
    query: str,
    policy: TraversalPolicy,
) -> StrategyRun:
    """Run an optional external baseline through a configured command template."""
    started = time.perf_counter()
    adapter, env_var, module_name = EXTERNAL_COMMANDS[strategy]
    metadata_payload: dict[str, str] = {
        "adapter": adapter,
        "config": env_var,
    }
    if util.find_spec(module_name) is not None:
        try:
            metadata_payload["dependency_version"] = metadata.version(module_name)
        except metadata.PackageNotFoundError:
            metadata_payload["dependency_version"] = "unknown"
    else:
        metadata_payload["dependency_version"] = "not_installed"

    command_template = os.environ.get(env_var, "")
    if not command_template:
        return StrategyRun(
            strategy=strategy,
            answer="",
            latency_ms=(time.perf_counter() - started) * 1000,
            nodes_visited=0,
            hops_taken=0,
            shard_fanout=0,
            tokens_estimated=estimate_tokens(query, []),
            warnings=[
                f"{adapter} external baseline skipped: set {env_var} "
                "to a command template containing {query}."
            ],
            external=True,
            skipped=True,
            metadata=metadata_payload,
        )

    command = command_template.format(query=shlex.quote(query))
    completed = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        timeout=max(1.0, policy.max_ms / 1000),
        check=False,
    )
    if completed.returncode != 0:
        return StrategyRun(
            strategy=strategy,
            answer="",
            latency_ms=(time.perf_counter() - started) * 1000,
            nodes_visited=0,
            hops_taken=0,
            shard_fanout=0,
            tokens_estimated=estimate_tokens(query, []),
            warnings=[f"{adapter} external baseline failed: {completed.stderr.strip()}"],
            external=True,
            skipped=True,
            metadata=metadata_payload,
        )
    answer, evidence = parse_external_stdout(completed.stdout)
    return StrategyRun(
        strategy=strategy,
        answer=answer,
        evidence=evidence,
        latency_ms=(time.perf_counter() - started) * 1000,
        nodes_visited=0,
        hops_taken=0,
        shard_fanout=0,
        tokens_estimated=estimate_tokens(query, evidence),
        warnings=[],
        external=True,
        skipped=False,
        metadata=metadata_payload,
    )


def parse_external_stdout(stdout: str) -> tuple[str, list[EvidenceSpan]]:
    """Parse optional JSON output from an external baseline command."""
    text = stdout.strip()
    if not text:
        return "", []
    try:
        payload = json.loads(text)
    except Exception:
        return text, []
    if not isinstance(payload, dict):
        return text, []
    evidence = [
        EvidenceSpan.model_validate(span)
        for span in payload.get("evidence", [])
        if isinstance(span, dict)
    ]
    return str(payload.get("answer", text)), evidence


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


def rerank_node_score(
    node: ConceptNode,
    query_terms: list[str],
    dense_scores: dict[str, float],
    bm25_scores: dict[str, float],
) -> float:
    """Score one hybrid-rerank candidate using dense, sparse, and evidence support."""
    query_set = set(query_terms)
    node_terms = set(tokenize(node.label + " " + node.text))
    evidence_terms = set(tokenize(" ".join(span.text for span in node.evidence)))
    lexical = len(query_set.intersection(node_terms)) / max(1, len(query_set))
    evidence_support = len(query_set.intersection(evidence_terms)) / max(1, len(query_set))
    return (
        0.36 * dense_scores.get(node.id, 0.0)
        + 0.34 * bm25_scores.get(node.id, 0.0)
        + 0.20 * lexical
        + 0.10 * evidence_support
    )


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
