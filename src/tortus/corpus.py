"""Built-in engineering corpus and chunking helpers."""

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


def load_builtin_corpus(name: str = "engineering") -> list[Document]:
    """Load load builtin corpus."""
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
    """Write write snapshot."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "documents.json").write_text(
        "[" + ",".join(document.model_dump_json() for document in documents) + "]\n",
        encoding="utf-8",
    )
    (out_dir / "chunks.jsonl").write_text(
        "\n".join(chunk.model_dump_json() for chunk in chunks) + "\n",
        encoding="utf-8",
    )
