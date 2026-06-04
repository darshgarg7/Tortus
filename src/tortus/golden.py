"""Candidate golden-set generation utilities."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GoldenScenario:
    """A reusable source-grounded multi-hop eval scenario."""

    slug: str
    topic: str
    expected_terms: tuple[str, ...]
    expected_sources: tuple[str, ...]
    expected_edge_types: tuple[str, ...]


SCENARIOS = (
    GoldenScenario(
        slug="auth-trace-incident",
        topic="service account token migration, gateway retries, and trace continuity",
        expected_terms=("token", "gateway", "trace", "propagation"),
        expected_sources=(
            "builtin://synthetic/incident-token-observability",
            "builtin://synthetic/gateway-retry-context",
            "builtin://opentelemetry/context-propagation",
        ),
        expected_edge_types=("portal",),
    ),
    GoldenScenario(
        slug="audience-dashboard",
        topic="audience validation dashboards and gateway retry behavior",
        expected_terms=("audience", "validation", "dashboard", "retry"),
        expected_sources=(
            "builtin://synthetic/auth-audience-validation",
            "builtin://synthetic/gateway-retry-context",
            "builtin://synthetic/runbook-auth-trace",
        ),
        expected_edge_types=("portal",),
    ),
    GoldenScenario(
        slug="token-projection-rollout",
        topic="bound token projection, validation rollout, and incident metrics",
        expected_terms=("projection", "validation", "metrics", "token"),
        expected_sources=(
            "builtin://kubernetes/kep-service-account-tokens",
            "builtin://synthetic/auth-audience-validation",
            "builtin://synthetic/incident-token-observability",
        ),
        expected_edge_types=("portal",),
    ),
    GoldenScenario(
        slug="cache-distractor",
        topic="gateway token cache tuning versus trace propagation failures",
        expected_terms=("cache", "gateway", "trace", "propagation"),
        expected_sources=(
            "builtin://synthetic/gateway-token-cache-distractor",
            "builtin://synthetic/gateway-retry-context",
            "builtin://opentelemetry/context-propagation",
        ),
        expected_edge_types=("portal",),
    ),
    GoldenScenario(
        slug="sidecar-distractor",
        topic="sidecar drain observability versus token audience failures",
        expected_terms=("sidecar", "shutdown", "token", "audience"),
        expected_sources=(
            "builtin://synthetic/sidecar-drain-observability",
            "builtin://synthetic/auth-audience-validation",
            "builtin://synthetic/incident-token-observability",
        ),
        expected_edge_types=("portal",),
    ),
    GoldenScenario(
        slug="legacy-secret-cleanup",
        topic="legacy secret cleanup versus bound service account token behavior",
        expected_terms=("legacy", "secret", "bound", "long-lived"),
        expected_sources=(
            "builtin://synthetic/legacy-secret-cleanup-distractor",
            "builtin://kubernetes/kep-service-account-tokens",
        ),
        expected_edge_types=("related_to",),
    ),
    GoldenScenario(
        slug="trace-sampling-distractor",
        topic="trace sampling policy versus fragmented gateway traces",
        expected_terms=("sampling", "fragmented", "gateway", "trace"),
        expected_sources=(
            "builtin://synthetic/trace-sampling-distractor",
            "builtin://synthetic/gateway-retry-context",
            "builtin://opentelemetry/context-propagation",
        ),
        expected_edge_types=("portal",),
    ),
    GoldenScenario(
        slug="runbook-correlation",
        topic="runbook correlation across audience metrics, retry logs, and propagation tests",
        expected_terms=("runbook", "metrics", "retry", "propagation"),
        expected_sources=(
            "builtin://synthetic/runbook-auth-trace",
            "builtin://synthetic/auth-audience-validation",
            "builtin://synthetic/gateway-retry-context",
        ),
        expected_edge_types=("portal", "related_to"),
    ),
    GoldenScenario(
        slug="policy-to-observability",
        topic="token policy crossing into observability investigation",
        expected_terms=("token", "policy", "observability", "incident"),
        expected_sources=(
            "builtin://kubernetes/kep-service-account-tokens",
            "builtin://synthetic/incident-token-observability",
            "builtin://opentelemetry/context-propagation",
        ),
        expected_edge_types=("portal",),
    ),
    GoldenScenario(
        slug="gateway-boundary",
        topic="gateway boundary behavior across authentication and propagation",
        expected_terms=("gateway", "authentication", "propagation", "boundary"),
        expected_sources=(
            "builtin://synthetic/gateway-retry-context",
            "builtin://synthetic/incident-token-observability",
            "builtin://opentelemetry/context-propagation",
        ),
        expected_edge_types=("portal",),
    ),
)

QUESTION_TEMPLATES = (
    "Which evidence path explains {topic}?",
    "Why does {topic} require more than vector-only retrieval?",
    "What source-backed path connects {topic}?",
    "How should an incident responder reason across {topic}?",
    "Which documents distinguish the root cause from distractors for {topic}?",
    "Where does the traversal need a portal hop for {topic}?",
    "What evidence would prove or reject the hypothesis about {topic}?",
    "How do the expected evidence spans line up for {topic}?",
    "Which cross-domain sources should be retrieved first for {topic}?",
    "Why is a single local chunk insufficient to explain {topic}?",
)


def generate_candidate_golden_set(count: int = 100) -> list[dict[str, Any]]:
    """Generate deterministic candidate golden questions with source URI labels."""
    rows: list[dict[str, Any]] = []
    for index in range(count):
        scenario = SCENARIOS[index % len(SCENARIOS)]
        template = QUESTION_TEMPLATES[(index // len(SCENARIOS)) % len(QUESTION_TEMPLATES)]
        rows.append(
            {
                "id": f"golden100-{index + 1:03d}-{scenario.slug}",
                "suite": "golden_candidate",
                "question": template.format(topic=scenario.topic),
                "expected_terms": list(scenario.expected_terms),
                "expected_sources": list(scenario.expected_sources),
                "expected_edge_types": list(scenario.expected_edge_types),
                "hop_count_target": 2 + (index % 2),
                "audit_status": "candidate_needs_human_review",
            }
        )
    return rows


def write_candidate_golden_set(path: Path, count: int = 100) -> None:
    """Write the deterministic candidate golden set to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = generate_candidate_golden_set(count=count)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
