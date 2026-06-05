"""Evaluation questions, runners, and scoring models."""

import json
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from .baselines import STRATEGIES, run_strategy
from .models import TraversalPolicy
from .text import token_set
from .traversal import QueryEngine


@dataclass(frozen=True)
class EvalQuestion:
    """One labeled retrieval evaluation question."""

    id: str
    suite: str
    question: str
    expected_terms: tuple[str, ...]
    expected_sources: tuple[str, ...]
    expected_edge_types: tuple[str, ...] = ()
    expect_answer: bool = True


SMOKE_QUESTIONS = (
    EvalQuestion(
        id="single-hop-auth",
        suite="single_hop",
        question="Why were bound service account tokens introduced?",
        expected_terms=("tokens", "risk", "long-lived"),
        expected_sources=("builtin://kubernetes/kep-service-account-tokens",),
    ),
    EvalQuestion(
        id="multi-hop-incident",
        suite="multi_hop",
        question="How did the token migration incident connect authentication and tracing?",
        expected_terms=("audience", "trace", "gateway"),
        expected_sources=(
            "builtin://synthetic/incident-token-observability",
            "builtin://opentelemetry/context-propagation",
            "builtin://kubernetes/kep-service-account-tokens",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="boundary-crossing-observability",
        suite="boundary_crossing",
        question="Why does context propagation matter when auth failures cross gateways?",
        expected_terms=("context", "gateway", "incident"),
        expected_sources=(
            "builtin://synthetic/incident-token-observability",
            "builtin://opentelemetry/context-propagation",
        ),
        expected_edge_types=("portal",),
    ),
)

GOLDEN_QUESTIONS = (
    EvalQuestion(
        id="golden-auth-trace-runbook",
        suite="multi_hop",
        question=(
            "Which runbook evidence connects wrong-audience service account tokens, "
            "gateway retries, and missing trace continuity?"
        ),
        expected_terms=("audience", "retry", "trace", "propagation"),
        expected_sources=(
            "builtin://synthetic/runbook-auth-trace",
            "builtin://synthetic/gateway-retry-context",
            "builtin://synthetic/auth-audience-validation",
        ),
        expected_edge_types=("portal", "related_to"),
    ),
    EvalQuestion(
        id="golden-distractor-token-cache",
        suite="boundary_crossing",
        question=(
            "Why is the gateway token cache guide insufficient for explaining the "
            "auth rollout tracing incident?"
        ),
        expected_terms=("cache", "trace", "incident", "propagation"),
        expected_sources=(
            "builtin://synthetic/gateway-token-cache-distractor",
            "builtin://synthetic/incident-token-observability",
            "builtin://synthetic/gateway-retry-context",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="golden-sidecar-not-root-cause",
        suite="boundary_crossing",
        question=(
            "Why is sidecar drain observability not the root cause of the token "
            "audience and trace propagation incident?"
        ),
        expected_terms=("sidecar", "token", "propagation", "incident"),
        expected_sources=(
            "builtin://synthetic/sidecar-drain-observability",
            "builtin://synthetic/incident-token-observability",
            "builtin://opentelemetry/context-propagation",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="golden-legacy-secret-distractor",
        suite="multi_hop",
        question=(
            "How should responders distinguish legacy secret cleanup from the gateway "
            "retry context propagation failure?"
        ),
        expected_terms=("legacy", "gateway", "retry", "propagation"),
        expected_sources=(
            "builtin://synthetic/legacy-secret-cleanup-distractor",
            "builtin://synthetic/gateway-retry-context",
            "builtin://synthetic/runbook-auth-trace",
        ),
        expected_edge_types=("portal",),
    ),
)

STRESS_QUESTIONS = (
    EvalQuestion(
        id="stress-audience-dashboard-retry",
        suite="stress",
        question="What evidence ties audience validation dashboards to gateway retry behavior?",
        expected_terms=("audience", "validation", "gateway", "retry"),
        expected_sources=(
            "builtin://synthetic/auth-audience-validation",
            "builtin://synthetic/gateway-retry-context",
            "builtin://synthetic/runbook-auth-trace",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="stress-trace-sampling-distractor",
        suite="stress",
        question="Why is trace sampling not enough to explain token audience failures?",
        expected_terms=("sampling", "token", "audience", "propagation"),
        expected_sources=(
            "builtin://synthetic/trace-sampling-distractor",
            "builtin://synthetic/incident-token-observability",
            "builtin://synthetic/auth-audience-validation",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="stress-sidecar-auth-boundary",
        suite="stress",
        question=(
            "How should a responder separate sidecar drain symptoms from auth rollout failures?"
        ),
        expected_terms=("sidecar", "token", "shutdown", "incident"),
        expected_sources=(
            "builtin://synthetic/sidecar-drain-observability",
            "builtin://synthetic/incident-token-observability",
            "builtin://synthetic/runbook-auth-trace",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="stress-token-projection-rollout",
        suite="stress",
        question=(
            "Which sources connect token projection, audience validation, and rollout metrics?"
        ),
        expected_terms=("projection", "audience", "validation", "metrics"),
        expected_sources=(
            "builtin://kubernetes/kep-service-account-tokens",
            "builtin://synthetic/auth-audience-validation",
            "builtin://synthetic/incident-token-observability",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="stress-fragmented-trace-gateway",
        suite="stress",
        question="Why do fragmented traces at a gateway point toward retry context propagation?",
        expected_terms=("fragmented", "gateway", "retry", "propagation"),
        expected_sources=(
            "builtin://opentelemetry/context-propagation",
            "builtin://synthetic/gateway-retry-context",
            "builtin://synthetic/runbook-auth-trace",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="stress-cache-guide-insufficient",
        suite="stress",
        question=(
            "Why is gateway token cache tuning insufficient for the trace continuity incident?"
        ),
        expected_terms=("cache", "gateway", "trace", "incident"),
        expected_sources=(
            "builtin://synthetic/gateway-token-cache-distractor",
            "builtin://synthetic/incident-token-observability",
            "builtin://opentelemetry/context-propagation",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="stress-legacy-secret-vs-bound-token",
        suite="stress",
        question="How do legacy secret cleanup and bound service account tokens differ?",
        expected_terms=("legacy", "secret", "bound", "long-lived"),
        expected_sources=(
            "builtin://synthetic/legacy-secret-cleanup-distractor",
            "builtin://kubernetes/kep-service-account-tokens",
        ),
        expected_edge_types=("related_to",),
    ),
    EvalQuestion(
        id="stress-policy-boundary-auth-trace",
        suite="stress",
        question=(
            "Which path crosses from token policy to trace propagation across a gateway boundary?"
        ),
        expected_terms=("token", "trace", "propagation", "gateway"),
        expected_sources=(
            "builtin://kubernetes/kep-service-account-tokens",
            "builtin://opentelemetry/context-propagation",
            "builtin://synthetic/gateway-retry-context",
        ),
        expected_edge_types=("portal",),
    ),
    EvalQuestion(
        id="stress-runbook-metrics",
        suite="stress",
        question="What runbook evidence joins audience metrics, retry logs, and propagation tests?",
        expected_terms=("audience", "metrics", "retry", "propagation"),
        expected_sources=(
            "builtin://synthetic/runbook-auth-trace",
            "builtin://synthetic/auth-audience-validation",
            "builtin://synthetic/gateway-retry-context",
        ),
        expected_edge_types=("portal", "related_to"),
    ),
)

NEGATIVE_QUESTIONS = (
    EvalQuestion(
        id="negative-unrelated-weather",
        suite="negative",
        question="What is tomorrow's weather forecast for Chicago?",
        expected_terms=(),
        expected_sources=(),
        expected_edge_types=(),
        expect_answer=False,
    ),
    EvalQuestion(
        id="negative-unsupported-finance",
        suite="negative",
        question="Which stock should I buy after the token migration incident?",
        expected_terms=(),
        expected_sources=(),
        expected_edge_types=(),
        expect_answer=False,
    ),
)


class EvalRow(BaseModel):
    """Scored result row for one question and strategy."""

    question_id: str
    suite: str
    strategy: str
    term_recall: float
    source_recall: float
    path_recall: float
    path_precision: float = 0.0
    faithfulness: float = 0.0
    latency_ms: float
    nodes_visited: int
    hops_taken: int
    portal_hops: int = 0
    shard_fanout: int
    shard_crossings: int = 0
    tokens_estimated: int
    path_edge_types: list[str] = Field(default_factory=list)
    warnings: list[str]
    expect_answer: bool = True

    @property
    def passed(self) -> bool:
        """Return whether this row satisfies the v1 evaluation threshold."""
        if not self.expect_answer:
            return self.faithfulness >= 1.0 and self.source_recall >= 1.0
        return (
            self.term_recall >= 0.5
            and self.source_recall >= 0.5
            and self.path_recall >= 0.5
            and self.faithfulness >= 0.5
        )


class EvalReport(BaseModel):
    """Collection of scored evaluation rows."""

    suite: str
    rows: list[EvalRow]

    def pass_rate(self, strategy: str | None = None) -> float:
        """Return pass rate."""
        rows = [row for row in self.rows if strategy is None or row.strategy == strategy]
        if not rows:
            return 0.0
        return sum(row.passed for row in rows) / len(rows)

    def strategies(self) -> list[str]:
        """Return strategies."""
        return sorted({row.strategy for row in self.rows})


def run_eval(
    engine: QueryEngine,
    suite: str = "smoke",
    strategies: tuple[str, ...] = STRATEGIES,
) -> EvalReport:
    """Run a suite across selected retrieval strategies."""
    rows: list[EvalRow] = []
    policy = TraversalPolicy(max_hops=3, max_nodes=32)
    questions = questions_for_suite(suite)
    for question in questions:
        for strategy in strategies:
            started = time.perf_counter()
            run = run_strategy(engine, question.question, strategy, policy=policy)
            latency_ms = (time.perf_counter() - started) * 1000
            evidence_text = " ".join(span.text.lower() for span in run.evidence)
            term_hits = sum(term in evidence_text for term in question.expected_terms)
            returned_sources = {span.uri for span in run.evidence}
            source_hits = len(returned_sources.intersection(question.expected_sources))
            path_hits = len(set(run.path_edge_types).intersection(question.expected_edge_types))
            path_recall = (
                path_hits / len(question.expected_edge_types)
                if question.expected_edge_types
                else 1.0
            )
            term_recall = (
                term_hits / len(question.expected_terms)
                if question.expected_terms
                else 1.0
            )
            source_recall = (
                source_hits / len(question.expected_sources)
                if question.expected_sources
                else (1.0 if not returned_sources else 0.0)
            )
            path_precision = score_path_precision(
                run.path_edge_types,
                returned_sources,
                question.expected_edge_types,
                question.expected_sources,
            )
            faithfulness = score_faithfulness(
                query=question.question,
                answer=run.answer,
                evidence=run.evidence,
                expect_answer=question.expect_answer,
            )
            rows.append(
                EvalRow(
                    question_id=question.id,
                    suite=question.suite,
                    strategy=strategy,
                    term_recall=term_recall,
                    source_recall=source_recall,
                    path_recall=path_recall,
                    path_precision=path_precision,
                    faithfulness=faithfulness,
                    latency_ms=latency_ms,
                    nodes_visited=run.nodes_visited,
                    hops_taken=run.hops_taken,
                    portal_hops=run.portal_hops,
                    shard_fanout=run.shard_fanout,
                    shard_crossings=run.shard_crossings,
                    tokens_estimated=run.tokens_estimated,
                    path_edge_types=run.path_edge_types,
                    warnings=run.warnings,
                    expect_answer=question.expect_answer,
                )
            )
    return EvalReport(suite=suite, rows=rows)


def run_smoke_eval(
    engine: QueryEngine,
    strategies: tuple[str, ...] = STRATEGIES,
) -> EvalReport:
    """Run the smoke suite across selected strategies."""
    return run_eval(engine, suite="smoke", strategies=strategies)


def questions_for_suite(suite: str) -> tuple[EvalQuestion, ...]:
    """Return labeled questions for a named suite."""
    if suite == "smoke":
        return SMOKE_QUESTIONS
    if suite == "golden":
        return GOLDEN_QUESTIONS
    if suite == "stress":
        return STRESS_QUESTIONS
    if suite == "negative":
        return NEGATIVE_QUESTIONS
    if suite == "golden100":
        return load_json_questions(Path("data/golden_set.json"))
    if suite == "full":
        return SMOKE_QUESTIONS + GOLDEN_QUESTIONS + STRESS_QUESTIONS + NEGATIVE_QUESTIONS
    if suite == "benchmark":
        return (
            SMOKE_QUESTIONS
            + GOLDEN_QUESTIONS
            + STRESS_QUESTIONS
            + NEGATIVE_QUESTIONS
            + load_json_questions(Path("data/golden_set.json"))
        )
    raise ValueError(f"unknown eval suite: {suite}")


def load_json_questions(path: Path) -> tuple[EvalQuestion, ...]:
    """Load labeled questions from a JSON golden-set file."""
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        EvalQuestion(
            id=str(row["id"]),
            suite=str(row.get("suite", "golden_candidate")),
            question=str(row["question"]),
            expected_terms=tuple(str(term) for term in row["expected_terms"]),
            expected_sources=tuple(str(source) for source in row["expected_sources"]),
            expected_edge_types=tuple(str(edge) for edge in row.get("expected_edge_types", ())),
            expect_answer=bool(row.get("expect_answer", True)),
        )
        for row in payload
    )


def score_path_precision(
    returned_edge_types: list[str],
    returned_sources: set[str],
    expected_edge_types: tuple[str, ...],
    expected_sources: tuple[str, ...],
) -> float:
    """Estimate how much of a returned path is relevant to the expected labels."""
    if not returned_edge_types:
        return 1.0 if not expected_edge_types else 0.0
    expected_edges = set(expected_edge_types)
    expected_source_set = set(expected_sources)
    edge_matches = sum(edge_type in expected_edges for edge_type in returned_edge_types)
    source_bonus = 1 if returned_sources.intersection(expected_source_set) else 0
    return min(1.0, (edge_matches + source_bonus) / max(1, len(returned_edge_types)))


def score_faithfulness(
    query: str,
    answer: str,
    evidence: Sequence[object],
    expect_answer: bool,
) -> float:
    """Score whether an answer is supported by its selected evidence."""
    withheld = "could not find enough source-backed evidence" in answer.lower()
    if not expect_answer:
        return 1.0 if withheld or not evidence else 0.0
    if withheld or not evidence:
        return 0.0
    answer_terms = token_set(answer)
    evidence_terms = token_set(" ".join(str(getattr(span, "text", "")) for span in evidence))
    query_terms = token_set(query)
    support_terms = answer_terms - query_terms
    if not support_terms:
        return 1.0
    supported = len(support_terms.intersection(evidence_terms))
    return supported / len(support_terms)


def parse_strategies(value: str) -> tuple[str, ...]:
    """Parse a comma-separated strategy selection."""
    if value == "all":
        return STRATEGIES
    requested = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = sorted(set(requested) - set(STRATEGIES))
    if unknown:
        raise ValueError(f"unknown eval strategies: {', '.join(unknown)}")
    return requested
