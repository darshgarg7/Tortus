"""Built-in engineering/public corpora and chunking helpers."""

from pathlib import Path

from .models import Chunk, Document, EvidenceSpan

ENGINEERING_CORPUS: tuple[Document, ...] = (
    Document(
        id="doc:kep-service-account-tokens",
        title="Kubernetes bound service account tokens",
        source="builtin://kubernetes/kep-service-account-tokens",
        domain="kubernetes-auth",
        text=(
            "Bound service account tokens were introduced to reduce risk from long-lived "
            "secrets mounted into pods. The design binds tokens to audience, time, and object "
            "identity so compromised credentials have a smaller blast radius. The migration "
            "requires API server validation changes, kubelet token projection, and clear "
            "compatibility behavior for workloads that still expect legacy secret tokens."
        ),
    ),
    Document(
        id="doc:kep-sidecar-containers",
        title="Kubernetes sidecar container lifecycle",
        source="builtin://kubernetes/kep-sidecar-containers",
        domain="kubernetes-workloads",
        text=(
            "Sidecar containers need startup and shutdown ordering that differs from normal "
            "init containers. The workload controller must preserve predictable lifecycle "
            "semantics while avoiding deadlocks during termination. Observability matters "
            "because operators need to explain why a pod remains running after application "
            "containers have exited."
        ),
    ),
    Document(
        id="doc:otel-context-propagation",
        title="OpenTelemetry context propagation",
        source="builtin://opentelemetry/context-propagation",
        domain="observability",
        text=(
            "Context propagation carries trace identifiers across service boundaries. The "
            "specification separates propagation format from SDK behavior so systems can "
            "interoperate across languages. Failures in propagation cause fragmented traces, "
            "which makes incident analysis harder when requests cross gateways and queues."
        ),
    ),
    Document(
        id="doc:incident-token-observability",
        title="Incident note: auth rollout degraded tracing",
        source="builtin://synthetic/incident-token-observability",
        domain="incident-analysis",
        text=(
            "During a service account token migration, a gateway started rejecting tokens "
            "with the wrong audience. The failed requests also lost trace continuity because "
            "the retry path did not preserve OpenTelemetry context. The resolution combined "
            "audience validation metrics, token projection documentation, and trace "
            "propagation tests across the gateway boundary."
        ),
    ),
    Document(
        id="doc:gateway-retry-context",
        title="Gateway retry context preservation",
        source="builtin://synthetic/gateway-retry-context",
        domain="platform-networking",
        text=(
            "Gateway retry handlers must copy traceparent and baggage headers when a request "
            "is retried after authentication middleware. If retry logic creates a fresh "
            "request without context propagation, distributed traces split at the gateway and "
            "incident responders lose the causal path between token validation and downstream "
            "service errors."
        ),
    ),
    Document(
        id="doc:auth-audience-validation",
        title="Audience validation rollout plan",
        source="builtin://synthetic/auth-audience-validation",
        domain="kubernetes-auth",
        text=(
            "Audience validation rejects tokens minted for the wrong service boundary. The "
            "rollout plan requires metrics for rejected audiences, compatibility checks for "
            "legacy projected tokens, and dashboards that correlate validation failures with "
            "gateway retry behavior."
        ),
    ),
    Document(
        id="doc:runbook-auth-trace",
        title="Runbook: correlate auth failures with trace breaks",
        source="builtin://synthetic/runbook-auth-trace",
        domain="incident-analysis",
        text=(
            "When authentication failures and fragmented traces appear together, responders "
            "should inspect token audience metrics, gateway retry logs, and OpenTelemetry "
            "context propagation tests. The runbook treats missing trace continuity as a "
            "symptom that the retry path may be dropping propagation headers."
        ),
    ),
    Document(
        id="doc:sidecar-drain-observability",
        title="Sidecar drain observability",
        source="builtin://synthetic/sidecar-drain-observability",
        domain="kubernetes-workloads",
        text=(
            "Sidecar shutdown can delay pod termination while log and proxy containers drain "
            "traffic. Operators need lifecycle events and trace spans to explain why an "
            "application container exited before the sidecar completed. This issue is about "
            "shutdown ordering, not token validation."
        ),
    ),
    Document(
        id="doc:gateway-token-cache-distractor",
        title="Gateway token cache tuning",
        source="builtin://synthetic/gateway-token-cache-distractor",
        domain="platform-networking",
        text=(
            "Gateway token caches reduce validation load by reusing recent authorization "
            "decisions. Cache eviction metrics mention tokens, audiences, gateways, and "
            "latency, but this tuning guide does not describe trace propagation or incident "
            "analysis across retries."
        ),
    ),
    Document(
        id="doc:trace-sampling-distractor",
        title="Trace sampling policy",
        source="builtin://synthetic/trace-sampling-distractor",
        domain="observability",
        text=(
            "Trace sampling policy controls how many spans are retained for high-volume "
            "services. Sampling errors can hide useful debugging data, but they do not explain "
            "why token audience validation fails or why gateway retries drop propagation "
            "headers."
        ),
    ),
    Document(
        id="doc:legacy-secret-cleanup-distractor",
        title="Legacy secret cleanup",
        source="builtin://synthetic/legacy-secret-cleanup-distractor",
        domain="kubernetes-auth",
        text=(
            "Legacy secret cleanup removes unused service account token secrets from old "
            "namespaces. The cleanup reduces credential sprawl and audit noise, but it is not "
            "part of the gateway retry incident and does not address OpenTelemetry context "
            "propagation."
        ),
    ),
)

PUBLIC_ENGINEERING_CORPUS: tuple[Document, ...] = (
    Document(
        id="doc:public-kubernetes-service-accounts",
        title="Kubernetes service account token projection",
        source="public://kubernetes/docs/service-accounts-admin@tortus-v1",
        domain="kubernetes-auth",
        metadata={
            "url": "https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of public Kubernetes documentation.",
        },
        text=(
            "Kubernetes service account token projection uses the TokenRequest API so pods "
            "receive bounded credentials instead of long-lived secret tokens. Operators must "
            "validate audiences, expiration, and object binding when migrating workloads. "
            "A failed migration often surfaces as authentication rejects at an API server or "
            "gateway boundary, so rollout plans need metrics and compatibility checks."
        ),
    ),
    Document(
        id="doc:public-kubernetes-projected-volumes",
        title="Kubernetes projected volumes and pod identity",
        source="public://kubernetes/docs/projected-volumes@tortus-v1",
        domain="kubernetes-auth",
        metadata={
            "url": "https://kubernetes.io/docs/concepts/storage/projected-volumes/",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of public Kubernetes documentation.",
        },
        text=(
            "Projected volumes can combine multiple sources into a pod volume, including a "
            "service account token with a configured audience and expiration. This lets the "
            "kubelet request credentials that fit a workload boundary. When the audience is "
            "wrong, downstream authentication middleware can reject the request even though "
            "the pod still has a token file."
        ),
    ),
    Document(
        id="doc:public-kubernetes-sidecars",
        title="Kubernetes sidecar container lifecycle",
        source="public://kubernetes/docs/sidecar-containers@tortus-v1",
        domain="kubernetes-workloads",
        metadata={
            "url": "https://kubernetes.io/docs/concepts/workloads/pods/sidecar-containers/",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of public Kubernetes documentation.",
        },
        text=(
            "Sidecar containers use lifecycle behavior that can keep a pod running after the "
            "main application container exits. Debugging this requires events, termination "
            "ordering, and observability data. Sidecar drain behavior can distract from token "
            "audience or trace propagation incidents because both can appear during rollouts."
        ),
    ),
    Document(
        id="doc:public-opentelemetry-context",
        title="OpenTelemetry context propagation",
        source="public://opentelemetry/spec/context@tortus-v1",
        domain="observability",
        metadata={
            "url": "https://opentelemetry.io/docs/specs/otel/context/",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of public OpenTelemetry documentation.",
        },
        text=(
            "OpenTelemetry context propagation carries execution-scoped identifiers across "
            "API boundaries so spans, baggage, metrics, and logs can be correlated. Services "
            "usually propagate trace context through headers such as traceparent and baggage. "
            "If retry middleware drops those carriers, a distributed trace can fragment at "
            "the exact boundary where an incident responder needs continuity."
        ),
    ),
    Document(
        id="doc:public-opentelemetry-baggage",
        title="OpenTelemetry baggage propagation",
        source="public://opentelemetry/docs/baggage@tortus-v1",
        domain="observability",
        metadata={
            "url": "https://opentelemetry.io/docs/concepts/signals/baggage/",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of public OpenTelemetry documentation.",
        },
        text=(
            "Baggage is contextual key-value data that travels with OpenTelemetry context. "
            "It can help correlate a request across services, but it can also leak sensitive "
            "or high-cardinality data when copied blindly. Gateways and retry handlers should "
            "preserve required context carriers while applying clear propagation policy."
        ),
    ),
    Document(
        id="doc:public-w3c-trace-context",
        title="W3C Trace Context",
        source="public://w3c/trace-context@tortus-v1",
        domain="observability",
        metadata={
            "url": "https://www.w3.org/TR/trace-context/",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of the public W3C recommendation.",
        },
        text=(
            "W3C Trace Context standardizes traceparent and tracestate headers so tracing "
            "systems can follow requests across process and service boundaries. A gateway "
            "that retries a request without copying traceparent breaks parent-child span "
            "relationships. That makes authentication failures harder to connect to later "
            "downstream errors."
        ),
    ),
    Document(
        id="doc:public-rfc9110-retries",
        title="RFC 9110 HTTP retries and idempotency",
        source="public://ietf/rfc9110@tortus-v1",
        domain="http-reliability",
        metadata={
            "url": "https://www.rfc-editor.org/rfc/rfc9110",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of public IETF HTTP semantics.",
        },
        text=(
            "HTTP semantics distinguish safe and idempotent methods, which matters when "
            "clients or gateways retry requests after network failures. Retry behavior should "
            "avoid duplicating side effects and should preserve request metadata needed for "
            "authentication and observability. Reliability policy therefore connects retry "
            "logic with token validation and trace propagation."
        ),
    ),
    Document(
        id="doc:public-rfc7807-problem-details",
        title="Problem details for HTTP APIs",
        source="public://ietf/rfc7807@tortus-v1",
        domain="http-reliability",
        metadata={
            "url": "https://www.rfc-editor.org/rfc/rfc7807",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of public IETF problem details.",
        },
        text=(
            "Problem details give HTTP APIs a consistent structure for machine-readable "
            "errors. Authentication middleware can use structured errors to expose rejected "
            "audiences or invalid token state without hiding the cause. When paired with "
            "trace identifiers, structured problem responses help incident responders join "
            "API errors to distributed traces."
        ),
    ),
    Document(
        id="doc:public-sre-retry-observability",
        title="Public SRE retry observability pattern",
        source="public://sre/retry-observability@tortus-v1",
        domain="incident-analysis",
        metadata={
            "url": "https://sre.google/sre-book/monitoring-distributed-systems/",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written summary of public SRE reliability guidance.",
        },
        text=(
            "Reliable systems treat retries as observable behavior rather than invisible "
            "control flow. Dashboards should show retry rates, authentication rejects, and "
            "trace continuity together when a rollout changes request identity. Without that "
            "combined view, teams can mistake symptoms such as latency or sampling changes "
            "for the root cause."
        ),
    ),
    Document(
        id="doc:public-cel-policy-rollout",
        title="Policy rollout and compatibility checks",
        source="public://architecture/policy-rollout@tortus-v1",
        domain="platform-policy",
        metadata={
            "url": "https://github.com/kubernetes/enhancements",
            "snapshot": "tortus-public-corpus-v1-2026-06-05",
            "content_note": "Author-written architecture note based on public rollout patterns.",
        },
        text=(
            "Policy rollouts should stage validation changes behind metrics, dry-run checks, "
            "and compatibility gates. For service identity, the rollout question is not only "
            "whether new tokens are valid, but whether every consumer expects the same "
            "audience, lifetime, and propagation behavior across gateways."
        ),
    ),
)

ACME_PAYMENTS_DEMO_CORPUS: tuple[Document, ...] = (
    Document(
        id="doc:acme-incident-eu-refund-tracing",
        title="Incident: EU Refund Trace Breakage",
        source="demo://acme-payments/incident-eu-refund-tracing",
        domain="payments-incident",
        metadata={"demo": "acme-payments"},
        text=(
            "On 2026-05-18, the EU refund workflow showed fragmented traces after the "
            "service account token migration. The refund API still completed most requests, "
            "but support could not follow a payment from refund-api to ledger-writer because "
            "the gateway retry path created a new trace segment. The incident appeared after "
            "the authentication team moved refund workers from long-lived service account "
            "secrets to projected short-lived tokens. The new tokens required the payments-api "
            "audience. When the gateway retried a request after an audience validation failure, "
            "it preserved the request body but dropped the traceparent header. Primary symptoms "
            "were trace continuity breaking only on retry, audience validation warnings "
            "increasing for EU refund workers, ledger writes succeeding after retry, and "
            "observability showing two unrelated traces. The mitigation was to align the refund "
            "worker audience with payments-api and preserve trace context across gateway retries."
        ),
    ),
    Document(
        id="doc:acme-auth-token-migration",
        title="Design Note: Service Account Token Migration",
        source="demo://acme-payments/auth-token-migration",
        domain="payments-auth",
        metadata={"demo": "acme-payments"},
        text=(
            "Refund workers are migrating from long-lived service account secrets to projected "
            "short-lived service account tokens. The new token model reduces secret exposure "
            "and allows the platform team to rotate credentials without redeploying every "
            "worker. The migration changes authentication behavior because each worker must "
            "request a token with the correct audience. For the payments stack, refund workers "
            "should use the payments-api audience before calling the gateway. If a worker "
            "presents a token with the legacy internal-api audience, the gateway can reject the "
            "first call and trigger a retry. The retry is expected to be safe only if request "
            "metadata, including trace context, is preserved. The rollout requires refund "
            "workers to request the payments-api audience, alerting on audience validation "
            "warnings, and coordination with observability because retry behavior can hide the "
            "original authentication failure."
        ),
    ),
    Document(
        id="doc:acme-gateway-retry-runbook",
        title="Runbook: Gateway Retry Context Preservation",
        source="demo://acme-payments/gateway-retry-runbook",
        domain="payments-gateway",
        metadata={"demo": "acme-payments"},
        text=(
            "The gateway retries idempotent payment requests when the first attempt fails with "
            "a transient authentication or upstream error. A retry must preserve request "
            "metadata so downstream services can correlate the second attempt with the original "
            "request. Required metadata on retry includes traceparent, tracestate, x-request-id, "
            "authenticated service account identity, and token audience used for the failed "
            "attempt. If traceparent is dropped during retry, observability will show a new "
            "trace even though the user operation is the same. If the retry follows an audience "
            "validation failure, responders should inspect both authentication logs and trace "
            "propagation logs. For refund incidents, the fastest check is to compare gateway "
            "retry logs with audience validation warnings from the refund worker."
        ),
    ),
    Document(
        id="doc:acme-observability-trace-context",
        title="Observability Note: Trace Context Propagation",
        source="demo://acme-payments/observability-trace-context",
        domain="payments-observability",
        metadata={"demo": "acme-payments"},
        text=(
            "The payments platform uses W3C trace context. Services must forward traceparent "
            "and tracestate across synchronous calls, retries, and queue handoffs. Trace "
            "continuity is especially important for incident response. If a gateway retry "
            "creates a fresh trace, the dashboard may show two healthy partial traces instead "
            "of one failing end-to-end operation. When trace continuity breaks after an "
            "authentication rollout, responders should verify whether token audience validation "
            "failed before the retry, whether the gateway preserved traceparent, whether "
            "downstream services received the same trace ID after retry, and whether the "
            "affected region adopted the token migration earlier than other regions. Missing "
            "retry trace context hides the causal path through authentication, gateway behavior, "
            "and downstream ledger writes."
        ),
    ),
)


def load_builtin_corpus(name: str = "engineering") -> list[Document]:
    """Load a built-in corpus by name."""
    if name == "engineering":
        return list(ENGINEERING_CORPUS)
    if name == "public":
        return list(PUBLIC_ENGINEERING_CORPUS)
    if name in {"acme-payments-demo", "demo-acme-payments", "demo"}:
        return list(ACME_PAYMENTS_DEMO_CORPUS)
    if name in {"public-engineering", "engineering-public", "all"}:
        return list(ENGINEERING_CORPUS + PUBLIC_ENGINEERING_CORPUS)
    if name != "engineering":
        raise ValueError(f"unknown built-in corpus: {name}")
    return list(ENGINEERING_CORPUS)


def chunk_document(document: Document, max_chars: int = 360) -> list[Chunk]:
    """Split a document into deterministic paragraph-sized chunks with evidence spans."""
    text = " ".join(document.text.split())
    chunks: list[Chunk] = []
    start = 0
    ordinal = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundary = text.rfind(". ", start, end)
            if boundary > start + 80:
                end = boundary + 1
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                Chunk(
                    id=f"{document.id}:chunk:{ordinal}",
                    document_id=document.id,
                    title=document.title,
                    domain=document.domain,
                    text=chunk_text,
                    evidence=EvidenceSpan(
                        uri=document.source,
                        start=start,
                        end=end,
                        text=chunk_text,
                    ),
                    ordinal=ordinal,
                    metadata=document.metadata,
                )
            )
            ordinal += 1
        start = end
        while start < len(text) and text[start].isspace():
            start += 1
    return chunks


def chunk_corpus(documents: list[Document], max_chars: int = 360) -> list[Chunk]:
    """Chunk chunk corpus."""
    return [
        chunk for document in documents for chunk in chunk_document(document, max_chars=max_chars)
    ]


def write_snapshot(documents: list[Document], chunks: list[Chunk], out_dir: Path) -> None:
    """Write source documents and chunks to a reproducible local snapshot."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "documents.json").write_text(
        "[" + ",".join(document.model_dump_json() for document in documents) + "]\n",
        encoding="utf-8",
    )
    (out_dir / "chunks.jsonl").write_text(
        "\n".join(chunk.model_dump_json() for chunk in chunks) + "\n",
        encoding="utf-8",
    )
