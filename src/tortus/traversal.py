"""Bounded query traversal, diagnostics, and evidence-grounded synthesis."""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .embeddings import EmbeddingProvider
from .graph_store import GraphStore
from .models import (
    AnswerClaim,
    AnswerResult,
    BaselineComparison,
    BudgetStats,
    ConceptNode,
    EdgeType,
    EvidenceSpan,
    PortalDecision,
    PrunedCandidate,
    ReasoningHop,
    RetrievalTrace,
    SearchHit,
    SemanticEdge,
    SourceHealth,
    TraversalPolicy,
)
from .sharding import ToroidalShardSimulator
from .text import overlap_terms, split_sentences, token_set
from .torus import torus_distance

logger = logging.getLogger(__name__)

OUT_OF_SCOPE_INTENT_TERMS = {
    "buy",
    "forecast",
    "investment",
    "portfolio",
    "stock",
    "tomorrow",
    "weather",
}
FRONTIER_BEAM_WIDTH = 5
MAX_SELECTED_EDGES_PER_NODE = 3
MAX_PORTALS_PER_NODE = 1


class SearchableIndex(Protocol):
    """Minimal vector-index interface used by the query engine."""

    def search(self, query_vector: np.ndarray, top_k: int = 8) -> list[SearchHit]:
        """Return ranked vector hits for a query embedding."""
        ...


@dataclass(frozen=True)
class EdgeScore:
    """Detailed score for a candidate traversal edge."""

    target: str
    score: float
    reason: str
    matched_terms: list[str]
    torus_distance: float | None
    components: dict[str, float]
    pruned: bool = False


@dataclass(frozen=True)
class SynthesizedAnswer:
    """An extractive answer plus support telemetry."""

    answer: str
    diagnosis: str
    root_cause_path: list[str]
    recommended_actions: list[str]
    missing_evidence: list[str]
    quality_mode: str
    evidence: list[EvidenceSpan]
    confidence: float
    lexical_support: int
    claims: list[AnswerClaim]
    unsupported_claims: list[AnswerClaim]


class ActionPlanEnhancer(Protocol):
    """Optional LLM-backed enhancer for diagnosis and action-plan fields."""

    quality_mode: str

    def enhance(self, query: str, synthesized: SynthesizedAnswer) -> SynthesizedAnswer:
        """Return an enhanced synthesized answer."""
        ...


class QueryEngine:
    """Execute bounded retrieval over the persisted graph and vector index."""

    def __init__(
        self,
        graph: GraphStore,
        index: SearchableIndex,
        embeddings: EmbeddingProvider,
        action_plan_enhancer: ActionPlanEnhancer | None = None,
        quality_mode: str = "deterministic-local",
    ) -> None:
        """Initialize the query engine dependencies."""
        self.graph = graph
        self.index = index
        self.embeddings = embeddings
        self.action_plan_enhancer = action_plan_enhancer
        self.quality_mode = quality_mode

    def answer(self, query: str, policy: TraversalPolicy | None = None) -> AnswerResult:
        """Retrieve evidence paths and synthesize a source-grounded answer."""
        policy = policy or TraversalPolicy()
        started = time.perf_counter()
        query_terms = token_set(query)
        query_vector = self.embeddings.embed([query])[0]
        seed_hits = self.index.search(query_vector, top_k=min(5, policy.max_nodes))
        nodes_by_id = {node.id: node for node in self.graph.list_nodes()}
        seed_hits = attach_hit_diagnostics(seed_hits, nodes_by_id, query_terms)
        seed_anchor = next(
            (nodes_by_id[hit.node_id] for hit in seed_hits if hit.node_id in nodes_by_id),
            None,
        )

        visited: set[str] = set()
        frontier: list[tuple[str, float, int, dict[str, float]]] = [
            (
                hit.node_id,
                hit.score + hit.score_components.get("lexical", 0.0),
                0,
                hit.score_components,
            )
            for hit in seed_hits
        ]
        hops: list[ReasoningHop] = []
        seen_hops: set[tuple[str, str, EdgeType]] = set()
        evidence: list[EvidenceSpan] = []
        best_hits: list[SearchHit] = []
        portal_hops = 0
        portal_candidates = 0
        candidates_considered = 0
        pruned_edges = 0
        selected_portals_by_node: dict[str, int] = {}
        pruned_candidates: list[PrunedCandidate] = []
        portal_decisions: list[PortalDecision] = []

        while frontier and len(visited) < policy.max_nodes:
            if (time.perf_counter() - started) * 1000 > policy.max_ms:
                break
            node_id, score, depth, components = frontier.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            node = nodes_by_id.get(node_id)
            if node is None:
                continue
            matched_terms = overlap_terms(
                query_terms,
                token_set(node.label + " " + node.text),
            )
            best_hits.append(
                SearchHit(
                    node_id=node.id,
                    label=node.label,
                    score=score,
                    evidence=node.evidence,
                    matched_terms=matched_terms,
                    score_components=components,
                )
            )
            evidence.extend(node.evidence)
            if depth >= policy.max_hops:
                continue

            neighbor_edges = self.graph.neighbors(node_id, local_only=policy.local_only)
            scored_edges = [
                (
                    edge,
                    score_edge(
                        edge=edge,
                        current=node,
                        nodes_by_id=nodes_by_id,
                        seed=seed_anchor,
                        query_terms=query_terms,
                        current_score=score,
                        policy=policy,
                    ),
                )
                for edge in neighbor_edges
            ]
            selected_edges_for_node = 0
            for edge, edge_score in sorted(
                scored_edges,
                key=lambda item: item[1].score,
                reverse=True,
            ):
                candidates_considered += 1
                target = edge_score.target
                if edge.edge_type == EdgeType.PORTAL:
                    portal_candidates += 1
                prune_reason = prune_reason_for_candidate(
                    target=target,
                    visited=visited,
                    edge=edge,
                    edge_score=edge_score,
                    current_score=score,
                    selected_edges_for_node=selected_edges_for_node,
                    portal_hops=portal_hops,
                    portal_candidates_by_node=selected_portals_by_node.get(node_id, 0),
                    policy=policy,
                )
                if prune_reason is not None:
                    pruned_edges += 1
                    record_pruned_candidate(
                        pruned_candidates,
                        edge=edge,
                        edge_score=edge_score,
                        from_node=node_id,
                        reason=prune_reason,
                    )
                    if edge.edge_type == EdgeType.PORTAL:
                        record_portal_decision(
                            portal_decisions,
                            edge_score=edge_score,
                            from_node=node_id,
                            selected=False,
                            reason=prune_reason,
                    )
                    continue
                if edge.edge_type == EdgeType.PORTAL:
                    portal_hops += 1
                    selected_portals_by_node[node_id] = selected_portals_by_node.get(node_id, 0) + 1
                    record_portal_decision(
                        portal_decisions,
                        edge_score=edge_score,
                        from_node=node_id,
                        selected=True,
                        reason=edge_score.reason,
                    )
                selected_edges_for_node += 1
                frontier.append((target, edge_score.score, depth + 1, edge_score.components))
                hop_key = (node_id, target, edge.edge_type)
                if policy.explain_hops and hop_key not in seen_hops:
                    seen_hops.add(hop_key)
                    hops.append(
                        ReasoningHop.model_validate(
                            {
                                "from": node_id,
                                "to": target,
                                "edge_type": edge.edge_type,
                                "weight": edge.weight,
                                "evidence": edge.evidence[:2],
                                "score": edge_score.score,
                                "reason": edge_score.reason,
                                "matched_terms": edge_score.matched_terms,
                                "torus_distance": edge_score.torus_distance,
                                "score_components": edge_score.components,
                            }
                        )
                    )
            frontier.sort(key=lambda item: item[1], reverse=True)
            if len(frontier) > FRONTIER_BEAM_WIDTH:
                for target, pruned_score, _, pruned_components in frontier[FRONTIER_BEAM_WIDTH:]:
                    pruned_edges += 1
                    pruned_candidates.append(
                        PrunedCandidate(
                            from_node=node_id,
                            to_node=target,
                            edge_type=EdgeType.RELATED_TO,
                            score=pruned_score,
                            reason="frontier_beam_pruned",
                            score_components=pruned_components,
                        )
                    )
                frontier = frontier[:FRONTIER_BEAM_WIDTH]
            if evidence_has_sufficient_coverage(query_terms, evidence) and len(visited) >= 4:
                break

        elapsed_ms = (time.perf_counter() - started) * 1000
        synthesized = synthesize_evidence_answer(
            query,
            best_hits[:8],
            evidence,
            quality_mode=self.quality_mode,
        )
        if self.action_plan_enhancer is not None:
            synthesized = self.action_plan_enhancer.enhance(query, synthesized)
        reported_hops = select_reasoning_hops(
            hops,
            query_terms=query_terms,
            evidence=synthesized.evidence,
            limit=min(policy.max_nodes, max(4, policy.max_hops * 2 + 2)),
        )
        warnings: list[str] = []
        if not synthesized.evidence:
            warnings.append("No evidence was retrieved; answer is intentionally withheld.")
        if elapsed_ms > policy.max_ms:
            warnings.append("Traversal exceeded the configured latency budget.")
        if len(visited) >= policy.max_nodes:
            warnings.append("Traversal reached the configured node budget.")
        if portal_hops > policy.max_portal_hops or (
            policy.max_portal_hops == 0 and portal_candidates > 0
        ):
            warnings.append("Traversal reached the configured portal-hop budget.")

        all_nodes = list(nodes_by_id.values())
        source_health = source_health_for_nodes(all_nodes)
        shard_simulator = ToroidalShardSimulator()
        visited_nodes = [node for node in all_nodes if node.id in visited]
        vector_baseline = BaselineComparison(
            name="vector_only",
            hits=seed_hits[:5],
            latency_ms=elapsed_ms,
        )
        diagnostics = {
            "seed_hits": [hit.model_dump(mode="json") for hit in seed_hits[:8]],
            "selected_evidence_sources": sorted({span.uri for span in synthesized.evidence}),
            "portal_candidates": portal_candidates,
            "pruned_edges": pruned_edges,
            "query_terms": sorted(query_terms),
            "raw_hops_considered": len(hops),
        }
        trace = RetrievalTrace(
            query_terms=sorted(query_terms),
            seed_hits=seed_hits[:8],
            selected_hops=reported_hops,
            pruned_candidates=pruned_candidates[:80],
            portal_decisions=portal_decisions[:80],
            evidence_spans=synthesized.evidence[:10],
            answer_claims=synthesized.claims,
            unsupported_claims=synthesized.unsupported_claims,
        )
        logger.info(
            "query_answered elapsed_ms=%.2f nodes=%s hops=%s portals=%s pruned=%s support=%s",
            elapsed_ms,
            len(visited),
            len(hops),
            portal_hops,
            pruned_edges,
            synthesized.lexical_support,
        )
        return AnswerResult(
            answer=synthesized.answer,
            diagnosis=synthesized.diagnosis,
            root_cause_path=synthesized.root_cause_path,
            recommended_actions=synthesized.recommended_actions,
            missing_evidence=synthesized.missing_evidence,
            quality_mode=synthesized.quality_mode,
            citations=synthesized.evidence[:10],
            confidence=synthesized.confidence,
            reasoning_path=reported_hops,
            evidence=synthesized.evidence[:10],
            budget=BudgetStats(
                elapsed_ms=elapsed_ms,
                nodes_visited=len(visited),
                hops_taken=len(reported_hops),
                portal_hops=portal_hops,
                shard_fanout=shard_simulator.fanout_for_nodes(visited_nodes),
                shard_crossings=shard_simulator.crossing_count(reported_hops, all_nodes),
                tokens_estimated=estimate_tokens(query, synthesized.evidence),
                candidates_considered=candidates_considered,
                pruned_edges=pruned_edges,
                portal_candidates=portal_candidates,
                lexical_support=synthesized.lexical_support,
                truncated=bool(warnings),
            ),
            warnings=warnings,
            baseline_comparison=[vector_baseline],
            source_health=source_health,
            trace=trace,
            diagnostics=diagnostics,
        )

    async def async_answer(
        self,
        query: str,
        policy: TraversalPolicy | None = None,
    ) -> AnswerResult:
        """Run answer generation without blocking an async web handler."""
        return await asyncio.to_thread(self.answer, query, policy)


def attach_hit_diagnostics(
    hits: list[SearchHit],
    nodes_by_id: dict[str, ConceptNode],
    query_terms: set[str],
) -> list[SearchHit]:
    """Attach lexical diagnostics to vector seed hits."""
    attached: list[SearchHit] = []
    for hit in hits:
        node = nodes_by_id.get(hit.node_id)
        text = f"{node.label} {node.text}" if node else ""
        matched = overlap_terms(query_terms, token_set(text))
        lexical = len(matched) / max(1, len(query_terms))
        attached.append(
            hit.model_copy(
                update={
                    "matched_terms": matched,
                    "score_components": {"dense": hit.score, "lexical": lexical},
                }
            )
        )
    return attached


def prune_reason_for_candidate(
    *,
    target: str,
    visited: set[str],
    edge: SemanticEdge,
    edge_score: EdgeScore,
    current_score: float,
    selected_edges_for_node: int,
    portal_hops: int,
    portal_candidates_by_node: int,
    policy: TraversalPolicy,
) -> str | None:
    """Return a prune reason for a candidate edge, or None if it should be selected."""
    if target in visited:
        return "already_visited"
    if edge_score.pruned:
        return edge_score.reason
    if selected_edges_for_node >= MAX_SELECTED_EDGES_PER_NODE:
        return "per_node_beam_width"
    if not edge_score.matched_terms and edge_score.score < current_score + 0.08:
        return "low_score_without_query_support"
    if edge.edge_type != EdgeType.PORTAL:
        return None
    if portal_hops >= policy.max_portal_hops:
        return "portal_budget"
    if portal_candidates_by_node >= MAX_PORTALS_PER_NODE:
        return "portal_per_node_limit"
    if not edge_score.matched_terms:
        return "portal_without_query_support"
    if edge_score.components.get("lexical", 0.0) < 0.20 and edge_score.score < current_score + 0.30:
        return "portal_weak_evidence_gain"
    return None


def record_pruned_candidate(
    candidates: list[PrunedCandidate],
    *,
    edge: SemanticEdge,
    edge_score: EdgeScore,
    from_node: str,
    reason: str,
) -> None:
    """Append a bounded pruned candidate trace row."""
    if len(candidates) >= 120:
        return
    candidates.append(
        PrunedCandidate(
            from_node=from_node,
            to_node=edge_score.target,
            edge_type=edge.edge_type,
            score=edge_score.score,
            reason=reason,
            matched_terms=edge_score.matched_terms,
            torus_distance=edge_score.torus_distance,
            score_components=edge_score.components,
        )
    )


def record_portal_decision(
    decisions: list[PortalDecision],
    *,
    edge_score: EdgeScore,
    from_node: str,
    selected: bool,
    reason: str,
) -> None:
    """Append a bounded portal decision trace row."""
    if len(decisions) >= 120:
        return
    decisions.append(
        PortalDecision(
            from_node=from_node,
            to_node=edge_score.target,
            selected=selected,
            score=edge_score.score,
            reason=reason,
            matched_terms=edge_score.matched_terms,
            score_components=edge_score.components,
        )
    )


def evidence_has_sufficient_coverage(query_terms: set[str], evidence: list[EvidenceSpan]) -> bool:
    """Return whether selected evidence covers enough query terms to stop expansion."""
    if not query_terms or len(evidence) < 4:
        return False
    evidence_terms = token_set(" ".join(span.text for span in evidence[-10:]))
    coverage = len(query_terms.intersection(evidence_terms)) / len(query_terms)
    return coverage >= 0.62


def select_reasoning_hops(
    hops: list[ReasoningHop],
    *,
    query_terms: set[str],
    evidence: list[EvidenceSpan],
    limit: int,
) -> list[ReasoningHop]:
    """Return a compact, high-support reasoning path from raw traversal expansions."""
    if len(hops) <= limit:
        return hops
    evidence_terms = token_set(" ".join(span.text for span in evidence))
    evidence_bonus_terms = query_terms.intersection(evidence_terms)

    def hop_score(hop: ReasoningHop) -> float:
        matched = set(hop.matched_terms)
        lexical = len(matched.intersection(query_terms)) / max(1, len(query_terms))
        evidence_bonus = 0.18 if matched.intersection(evidence_bonus_terms) else 0.0
        portal_bonus = 0.22 if hop.edge_type == EdgeType.PORTAL else 0.0
        support_bonus = 0.14 if hop.evidence else 0.0
        distance_penalty = min(0.18, (hop.torus_distance or 0.0) / 20.0)
        return (
            hop.score
            + lexical
            + evidence_bonus
            + portal_bonus
            + support_bonus
            - distance_penalty
        )

    ranked = sorted(hops, key=hop_score, reverse=True)
    selected: list[ReasoningHop] = []
    seen_nodes: set[str] = set()
    for hop in ranked:
        introduces_node = hop.from_node not in seen_nodes or hop.to_node not in seen_nodes
        if introduces_node or hop.edge_type == EdgeType.PORTAL:
            selected.append(hop)
            seen_nodes.update({hop.from_node, hop.to_node})
        if len(selected) >= limit:
            break
    if not any(hop.edge_type == EdgeType.PORTAL for hop in selected):
        portal = next((hop for hop in ranked if hop.edge_type == EdgeType.PORTAL), None)
        if portal is not None:
            selected = [portal, *selected[: max(0, limit - 1)]]
    if not any(hop.edge_type == EdgeType.RELATED_TO for hop in selected):
        related = next((hop for hop in ranked if hop.edge_type == EdgeType.RELATED_TO), None)
        if related is not None and related not in selected:
            selected = [*selected[: max(0, limit - 1)], related]
    return sorted(selected, key=lambda hop: hops.index(hop))


def score_edge(
    edge: SemanticEdge,
    current: ConceptNode,
    nodes_by_id: dict[str, ConceptNode],
    seed: ConceptNode | None,
    query_terms: set[str],
    current_score: float,
    policy: TraversalPolicy,
) -> EdgeScore:
    """Score one candidate edge using lexical support, edge weight, and torus locality."""
    target_id = edge.target if edge.source == current.id else edge.source
    target = nodes_by_id.get(target_id)
    if target is None:
        return EdgeScore(
            target=target_id,
            score=0.0,
            reason="missing_target",
            matched_terms=[],
            torus_distance=None,
            components={},
            pruned=True,
        )

    target_terms = token_set(target.label + " " + target.text)
    matched_terms = set(overlap_terms(query_terms, target_terms))
    shared_terms = {str(term) for term in edge.metadata.get("shared_terms", [])}
    shared_phrase = str(edge.metadata.get("shared_phrase", edge.metadata.get("shared_term", "")))
    matched_terms.update(query_terms.intersection(shared_terms))
    matched_terms.update(query_terms.intersection(token_set(shared_phrase)))
    matched = sorted(matched_terms)

    lexical = len(matched) / max(1, len(query_terms))
    distance = (
        torus_distance(current.torus, target.torus)
        if current.torus and target.torus
        else None
    )
    torus_locality = max(0.0, 1.0 - (distance / np.pi)) if distance is not None else 0.0
    seed_distance = (
        torus_distance(seed.torus, target.torus)
        if seed and seed.torus and target.torus
        else None
    )
    seed_locality = max(0.0, 1.0 - (seed_distance / np.pi)) if seed_distance is not None else 0.0
    portal = edge.edge_type == EdgeType.PORTAL
    portal_adjustment = 0.10 if portal and matched else 0.0
    if portal and not matched:
        portal_adjustment = -0.22
    group_bonus = group_match_bonus(target, policy)
    score = (
        current_score * 0.42
        + edge.weight * 0.34
        + lexical * 0.48
        + torus_locality * 0.16
        + seed_locality * 0.08
        + portal_adjustment
        + group_bonus
    )
    pruned = portal and not matched
    reason = str(edge.metadata.get("reason", "scored_neighbor"))
    if portal and matched:
        reason = "portal_matched_query_terms"
    elif portal and pruned:
        reason = "portal_pruned_no_query_support"
    components = {
        "previous": current_score,
        "edge_weight": edge.weight,
        "lexical": lexical,
        "torus_locality": torus_locality,
        "seed_locality": seed_locality,
        "portal_adjustment": portal_adjustment,
        "group_bonus": group_bonus,
    }
    return EdgeScore(
        target=target_id,
        score=float(score),
        reason=reason,
        matched_terms=matched,
        torus_distance=distance,
        components=components,
        pruned=pruned,
    )


def group_match_bonus(node: ConceptNode, policy: TraversalPolicy) -> float:
    """Score an optional semantic-group preference."""
    if not policy.semantic_group:
        return 0.0
    for membership in node.memberships:
        if membership.subgraph == policy.semantic_group:
            return 0.10 * membership.weight
    return 0.0


def synthesize_evidence_answer(
    query: str,
    hits: list[SearchHit],
    evidence: list[EvidenceSpan],
    quality_mode: str = "deterministic-local",
) -> SynthesizedAnswer:
    """Build a concise extractive answer using only supported evidence spans."""
    if token_set(query).intersection(OUT_OF_SCOPE_INTENT_TERMS):
        missing = missing_evidence_for_query(query, [], 0)
        unsupported = [
            AnswerClaim(
                text="I could not find enough source-backed evidence to answer this query.",
                supported=False,
            )
        ]
        return SynthesizedAnswer(
            answer="I could not find enough source-backed evidence to answer this query.",
            diagnosis="Tortus could not ground this question in the indexed sources.",
            root_cause_path=[],
            recommended_actions=[
                "Add source documents that directly describe the system, incident, "
                "and intended fix."
            ],
            missing_evidence=missing,
            quality_mode=quality_mode,
            evidence=[],
            confidence=0.0,
            lexical_support=0,
            claims=unsupported,
            unsupported_claims=unsupported,
        )
    supported = [item for item in rank_evidence(query, dedupe_evidence(evidence)) if item[0] > 0]
    if not supported:
        missing = missing_evidence_for_query(query, [], 0)
        unsupported = [
            AnswerClaim(
                text="I could not find enough source-backed evidence to answer this query.",
                supported=False,
            )
        ]
        return SynthesizedAnswer(
            answer="I could not find enough source-backed evidence to answer this query.",
            diagnosis="Tortus could not find enough source-backed overlap to diagnose the issue.",
            root_cause_path=[],
            recommended_actions=[
                "Add the incident timeline, design note, runbook, or owner notes "
                "that mention the affected terms."
            ],
            missing_evidence=missing,
            quality_mode=quality_mode,
            evidence=[],
            confidence=0.0,
            lexical_support=0,
            claims=unsupported,
            unsupported_claims=unsupported,
        )
    selected = [span for _, span in supported[:6]]
    sentences = select_supporting_sentences(query, selected)
    if not sentences:
        missing = missing_evidence_for_query(query, selected, 0)
        unsupported = [
            AnswerClaim(
                text="I could not find enough source-backed evidence to answer this query.",
                supported=False,
            )
        ]
        return SynthesizedAnswer(
            answer="I could not find enough source-backed evidence to answer this query.",
            diagnosis="The retrieved sources were not specific enough to support a diagnosis.",
            root_cause_path=[],
            recommended_actions=[
                "Add more specific source text that names the failure mode, affected "
                "component, and attempted fix."
            ],
            missing_evidence=missing,
            quality_mode=quality_mode,
            evidence=[],
            confidence=0.0,
            lexical_support=0,
            claims=unsupported,
            unsupported_claims=unsupported,
        )
    labels = ", ".join(hit.label for hit in hits[:3])
    source_count = len({span.uri for span in selected})
    body = " ".join(sentences[:4])
    lexical_support = sum(score for score, _ in supported[:6])
    confidence = min(0.95, 0.32 + 0.10 * len(selected) + 0.04 * min(5, lexical_support))
    answer = (
        f"{body} The strongest retrieved concepts are {labels}. "
        f"This answer is grounded in {source_count} source(s)."
    )
    claims = claims_for_answer(answer, selected, query)
    missing = missing_evidence_for_query(query, selected, lexical_support)
    return SynthesizedAnswer(
        answer=answer,
        diagnosis=diagnosis_for_evidence(sentences, selected),
        root_cause_path=root_cause_path_for_hits(hits, selected),
        recommended_actions=recommended_actions_for_evidence(query, selected),
        missing_evidence=missing,
        quality_mode=quality_mode,
        evidence=selected,
        confidence=confidence,
        lexical_support=lexical_support,
        claims=claims,
        unsupported_claims=[claim for claim in claims if not claim.supported],
    )


def rank_evidence(query: str, evidence: list[EvidenceSpan]) -> list[tuple[int, EvidenceSpan]]:
    """Rank evidence spans by query-term overlap."""
    query_terms = token_set(query)
    scored = [(len(query_terms.intersection(token_set(span.text))), span) for span in evidence]
    return sorted(scored, key=lambda item: (item[0], len(item[1].text)), reverse=True)


def select_supporting_sentences(query: str, evidence: list[EvidenceSpan]) -> list[str]:
    """Choose source sentences that contain query-relevant terms."""
    query_terms = token_set(query)
    sentences: list[tuple[int, str]] = []
    for span in evidence:
        for sentence in split_sentences(span.text):
            support = len(query_terms.intersection(token_set(sentence)))
            if support > 0:
                sentences.append((support, sentence))
    sentences.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
    selected: list[str] = []
    seen: set[str] = set()
    for _, sentence in sentences:
        if sentence not in seen:
            selected.append(sentence)
            seen.add(sentence)
        if len(selected) >= 4:
            break
    return selected


def claims_for_answer(answer: str, evidence: list[EvidenceSpan], query: str) -> list[AnswerClaim]:
    """Score each answer sentence against selected evidence spans."""
    query_terms = token_set(query)
    claims: list[AnswerClaim] = []
    for sentence in split_sentences(answer):
        sentence_terms = token_set(sentence) - query_terms
        supporting_spans = [
            span
            for span in evidence
            if sentence_terms and len(sentence_terms.intersection(token_set(span.text))) >= 1
        ]
        if not sentence_terms and evidence:
            supporting_spans = evidence[:1]
        claims.append(
            AnswerClaim(
                text=sentence,
                supported=bool(supporting_spans),
                support_count=len(supporting_spans),
                evidence_uris=sorted({span.uri for span in supporting_spans}),
            )
        )
    return claims


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


def diagnosis_for_evidence(sentences: list[str], evidence: list[EvidenceSpan]) -> str:
    """Return a compact diagnosis from selected evidence sentences."""
    if not sentences:
        return "Tortus found evidence, but not enough sentence-level support for a diagnosis."
    source_count = len({span.uri for span in evidence})
    return (
        " ".join(sentences[:2]).strip()
        + f" This diagnosis is grounded in {source_count} cited source(s)."
    )


def root_cause_path_for_hits(hits: list[SearchHit], evidence: list[EvidenceSpan]) -> list[str]:
    """Return a compact root-cause path label list for user-facing output."""
    labels: list[str] = []
    for hit in hits:
        if hit.label and hit.label not in labels:
            labels.append(hit.label)
        if len(labels) >= 4:
            break
    for span in evidence:
        uri = span.uri
        if uri not in labels:
            labels.append(uri)
        if len(labels) >= 6:
            break
    return labels


def recommended_actions_for_evidence(query: str, evidence: list[EvidenceSpan]) -> list[str]:
    """Derive conservative next actions from cited evidence."""
    joined = " ".join(span.text for span in evidence).lower()
    query_terms = token_set(query)
    actions: list[str] = []
    if {"token", "tokens", "audience", "auth", "authentication"}.intersection(query_terms) or {
        "token",
        "audience",
        "authentication",
    }.intersection(token_set(joined)):
        actions.append(
            "Verify token audience, issuer, and service-boundary expectations for the "
            "affected path."
        )
    if {"trace", "tracing", "traceparent", "opentelemetry"}.intersection(query_terms) or {
        "trace",
        "traceparent",
        "opentelemetry",
    }.intersection(token_set(joined)):
        actions.append(
            "Add or rerun trace-context propagation checks across retries and service boundaries."
        )
    if "retry" in query_terms or "retry" in joined:
        actions.append("Audit retry/failover code paths for dropped headers or recreated requests.")
    if "metrics" in joined or "dashboard" in joined:
        actions.append("Correlate the cited metrics or dashboards with the incident timeline.")
    actions.append(
        "Turn the cited evidence path into a ticket or runbook update for the owning team."
    )
    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped[:5]


def missing_evidence_for_query(
    query: str,
    evidence: list[EvidenceSpan],
    lexical_support: int,
) -> list[str]:
    """Return missing-context warnings that keep the answer honest."""
    missing: list[str] = []
    source_count = len({span.uri for span in evidence})
    if source_count < 2:
        missing.append("Add at least one independent source so Tortus can verify the path.")
    if lexical_support < 3:
        terms = ", ".join(sorted(token_set(query))[:6])
        missing.append(f"Add source text that explicitly mentions the query terms: {terms}.")
    if not evidence:
        missing.append(
            "Add an incident note, design note, runbook, or support ticket for this case."
        )
    return missing


def source_health_for_nodes(nodes: list[ConceptNode]) -> SourceHealth:
    """Estimate source health from persisted graph-node metadata."""
    document_ids = {node.document_id for node in nodes}
    source_types: dict[str, int] = {}
    warnings: set[str] = set()
    normalized_hashes: dict[str, int] = {}
    empty_documents: set[str] = set()
    for node in nodes:
        source_metadata = node.metadata.get("source_metadata", {})
        if isinstance(source_metadata, dict):
            source_type = str(source_metadata.get("source_type", "builtin"))
            source_types[source_type] = source_types.get(source_type, 0) + 1
            for warning in source_metadata.get("warnings", []):
                warnings.add(str(warning))
            normalized_sha = str(source_metadata.get("normalized_sha256", ""))
            if normalized_sha:
                normalized_hashes[normalized_sha] = normalized_hashes.get(normalized_sha, 0) + 1
        if not node.text.strip():
            empty_documents.add(node.document_id)
    duplicate_documents = sum(1 for count in normalized_hashes.values() if count > 1)
    penalty = (
        min(0.35, 0.05 * len(warnings))
        + min(0.25, 0.08 * len(empty_documents))
        + min(0.20, 0.04 * duplicate_documents)
    )
    return SourceHealth(
        documents=len(document_ids),
        chunks=len(nodes),
        supported_sources=len(document_ids),
        empty_documents=len(empty_documents),
        duplicate_documents=duplicate_documents,
        warnings=sorted(warnings)[:20],
        source_types=source_types or {"builtin": len(nodes)},
        quality_score=max(0.0, 1.0 - penalty),
    )


def estimate_tokens(query: str, evidence: list[EvidenceSpan]) -> int:
    """Estimate the token count of a prompt context using a fast heuristic."""
    text = query + " " + " ".join(span.text for span in evidence[:10])
    return int(np.ceil(len(text.split()) * 1.35))
