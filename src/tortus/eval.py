"""Evaluation questions, runners, and scoring models."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from .baselines import STRATEGIES, run_strategy
from .models import TraversalPolicy
from .traversal import QueryEngine


@dataclass(frozen=True)
class EvalQuestion:
    """Represent EvalQuestion data."""

    id: str
    suite: str
    question: str
    expected_terms: tuple[str, ...]
    expected_sources: tuple[str, ...]
    expected_edge_types: tuple[str, ...] = ()


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


class EvalRow(BaseModel):
    """Represent EvalRow data."""

    question_id: str
    suite: str
    strategy: str
    term_recall: float
    source_recall: float
    path_recall: float
    latency_ms: float
    nodes_visited: int
    hops_taken: int
    portal_hops: int = 0
    shard_fanout: int
    shard_crossings: int = 0
    tokens_estimated: int
    warnings: list[str]

    @property
    def passed(self) -> bool:
        """Return passed."""
        return self.term_recall >= 0.5 and self.source_recall >= 0.5 and self.path_recall >= 0.5


class EvalReport(BaseModel):
    """Represent EvalReport data."""

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
    """Run run eval."""
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
            rows.append(
                EvalRow(
                    question_id=question.id,
                    suite=question.suite,
                    strategy=strategy,
                    term_recall=term_hits / len(question.expected_terms),
                    source_recall=source_hits / len(question.expected_sources),
                    path_recall=path_recall,
                    latency_ms=latency_ms,
                    nodes_visited=run.nodes_visited,
                    hops_taken=run.hops_taken,
                    portal_hops=run.portal_hops,
                    shard_fanout=run.shard_fanout,
                    shard_crossings=run.shard_crossings,
                    tokens_estimated=run.tokens_estimated,
                    warnings=run.warnings,
                )
            )
    return EvalReport(suite=suite, rows=rows)


def run_smoke_eval(
    engine: QueryEngine,
    strategies: tuple[str, ...] = STRATEGIES,
) -> EvalReport:
    """Run run smoke eval."""
    return run_eval(engine, suite="smoke", strategies=strategies)


def questions_for_suite(suite: str) -> tuple[EvalQuestion, ...]:
    """Return questions for suite."""
    if suite == "smoke":
        return SMOKE_QUESTIONS
    if suite == "golden":
        return GOLDEN_QUESTIONS
    if suite == "stress":
        return STRESS_QUESTIONS
    if suite == "golden100":
        return load_json_questions(Path("data/golden_set.json"))
    if suite == "full":
        return SMOKE_QUESTIONS + GOLDEN_QUESTIONS + STRESS_QUESTIONS
    if suite == "benchmark":
        return (
            SMOKE_QUESTIONS
            + GOLDEN_QUESTIONS
            + STRESS_QUESTIONS
            + load_json_questions(Path("data/golden_set.json"))
        )
    raise ValueError(f"unknown eval suite: {suite}")


def load_json_questions(path: Path) -> tuple[EvalQuestion, ...]:
    """Load load json questions."""
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
        )
        for row in payload
    )


def parse_strategies(value: str) -> tuple[str, ...]:
    """Parse parse strategies."""
    if value == "all":
        return STRATEGIES
    requested = tuple(item.strip() for item in value.split(",") if item.strip())
    unknown = sorted(set(requested) - set(STRATEGIES))
    if unknown:
        raise ValueError(f"unknown eval strategies: {', '.join(unknown)}")
    return requested
