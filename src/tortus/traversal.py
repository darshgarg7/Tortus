"""Bounded query traversal and answer synthesis."""

import time

import numpy as np

from .embeddings import EmbeddingProvider
from .graph_store import GraphStore
from .models import (
    AnswerResult,
    BaselineComparison,
    BudgetStats,
    EdgeType,
    EvidenceSpan,
    ReasoningHop,
    SearchHit,
    TraversalPolicy,
)
from .sharding import ToroidalShardSimulator
from .vector import ExactVectorIndex


class QueryEngine:
    """Engine for executing bounded graph traversal and answering queries."""

    def __init__(
        self,
        graph: GraphStore,
        index: ExactVectorIndex,
        embeddings: EmbeddingProvider,
    ) -> None:
        """Initialize the query engine dependencies."""
        self.graph = graph
        self.index = index
        self.embeddings = embeddings

    def answer(self, query: str, policy: TraversalPolicy | None = None) -> AnswerResult:
        """Execute a query by seeding vectors and traversing the graph under budget constraints."""
        policy = policy or TraversalPolicy()
        started = time.perf_counter()
        query_vector = self.embeddings.embed([query])[0]
        seed_hits = self.index.search(query_vector, top_k=min(8, policy.max_nodes))

        visited: set[str] = set()
        frontier: list[tuple[str, float, int]] = [(hit.node_id, hit.score, 0) for hit in seed_hits]
        hops: list[ReasoningHop] = []
        seen_hops: set[tuple[str, str, EdgeType]] = set()
        evidence: list[EvidenceSpan] = []
        best_hits: list[SearchHit] = []
        portal_hops = 0

        while frontier and len(visited) < policy.max_nodes:
            if (time.perf_counter() - started) * 1000 > policy.max_ms:
                break
            node_id, score, depth = frontier.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            node = self.graph.get_node(node_id)
            if node is None:
                continue
            best_hits.append(
                SearchHit(
                    node_id=node.id,
                    label=node.label,
                    score=score,
                    evidence=node.evidence,
                )
            )
            evidence.extend(node.evidence)
            if depth >= policy.max_hops:
                continue
            for edge in self.graph.neighbors(node_id, local_only=policy.local_only):
                target = edge.target if edge.source == node_id else edge.source
                if target in visited:
                    continue
                if edge.edge_type == EdgeType.PORTAL and portal_hops >= policy.max_portal_hops:
                    continue
                edge_bonus = 0.08 if edge.edge_type == EdgeType.PORTAL else 0.03
                next_score = score * 0.82 + edge.weight + edge_bonus
                frontier.append((target, next_score, depth + 1))
                hop_key = (node_id, target, edge.edge_type)
                if policy.explain_hops and hop_key not in seen_hops:
                    seen_hops.add(hop_key)
                    if edge.edge_type == EdgeType.PORTAL:
                        portal_hops += 1
                    hops.append(
                        ReasoningHop.model_validate(
                            {
                                "from": node_id,
                                "to": target,
                                "edge_type": edge.edge_type,
                                "weight": edge.weight,
                                "evidence": edge.evidence[:2],
                            }
                        )
                    )
            frontier.sort(key=lambda item: item[1], reverse=True)

        elapsed_ms = (time.perf_counter() - started) * 1000
        warnings: list[str] = []
        if not evidence:
            warnings.append("No evidence was retrieved; answer is intentionally withheld.")
        if elapsed_ms > policy.max_ms:
            warnings.append("Traversal exceeded the configured latency budget.")
        if len(visited) >= policy.max_nodes:
            warnings.append("Traversal reached the configured node budget.")
        if portal_hops >= policy.max_portal_hops:
            warnings.append("Traversal reached the configured portal-hop budget.")

        answer = synthesize_evidence_answer(query, best_hits[:6], evidence[:6])
        confidence = min(0.92, 0.35 + 0.07 * len(best_hits) + 0.03 * len(hops))
        all_nodes = self.graph.list_nodes()
        shard_simulator = ToroidalShardSimulator()
        visited_nodes = [node for node in all_nodes if node.id in visited]
        shard_fanout = shard_simulator.fanout_for_nodes(visited_nodes)
        shard_crossings = shard_simulator.crossing_count(hops, all_nodes)
        vector_baseline = BaselineComparison(
            name="vector_only",
            hits=seed_hits[:5],
            latency_ms=elapsed_ms,
        )
        return AnswerResult(
            answer=answer,
            confidence=confidence if evidence else 0.0,
            reasoning_path=hops[: policy.max_nodes],
            evidence=dedupe_evidence(evidence)[:10],
            budget=BudgetStats(
                elapsed_ms=elapsed_ms,
                nodes_visited=len(visited),
                hops_taken=len(hops),
                portal_hops=portal_hops,
                shard_fanout=shard_fanout,
                shard_crossings=shard_crossings,
                tokens_estimated=estimate_tokens(query, evidence),
                truncated=bool(warnings),
            ),
            warnings=warnings,
            baseline_comparison=[vector_baseline],
        )


def synthesize_evidence_answer(
    query: str,
    hits: list[SearchHit],
    evidence: list[EvidenceSpan],
) -> str:
    """Synthesize a natural language answer grounded strictly in retrieved evidence spans."""
    if not evidence:
        return "I could not find enough source-backed evidence to answer this query."
    labels = ", ".join(hit.label for hit in hits[:3])
    source_count = len({span.uri for span in evidence})
    return (
        f"Tortus found a source-backed path for: {query!r}. "
        f"The strongest concepts are {labels}. "
        f"The answer is grounded in {source_count} source(s), with the reasoning path exposed "
        "for audit instead of hidden inside the prompt."
    )


def dedupe_evidence(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    """Remove duplicate evidence spans from the traversal frontier."""
    seen: set[tuple[str, int, int]] = set()
    unique: list[EvidenceSpan] = []
    for span in spans:
        key = (span.uri, span.start, span.end)
        if key not in seen:
            seen.add(key)
            unique.append(span)
    return unique


def estimate_tokens(query: str, evidence: list[EvidenceSpan]) -> int:
    """Estimate the token count of a prompt context using a fast heuristic."""
    text = query + " " + " ".join(span.text for span in evidence[:10])
    return int(np.ceil(len(text.split()) * 1.35))
