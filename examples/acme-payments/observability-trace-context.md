# Observability Note: Trace Context Propagation

The payments platform uses W3C trace context. Services must forward `traceparent` and `tracestate` across synchronous calls, retries, and queue handoffs.

Trace continuity is especially important for incident response. If a gateway retry creates a fresh trace, the dashboard may show two healthy partial traces instead of one failing end-to-end operation.

When trace continuity breaks after an authentication rollout, responders should verify:

- whether token audience validation failed before the retry
- whether the gateway preserved `traceparent`
- whether downstream services received the same trace ID after retry
- whether the affected region adopted the token migration earlier than other regions

The observability team treats missing retry trace context as a reliability issue, not only a dashboard issue, because it hides the causal path through authentication, gateway behavior, and downstream ledger writes.
