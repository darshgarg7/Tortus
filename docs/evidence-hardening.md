# Evidence Hardening Plan

Tortus currently has a working v0 harness, not a publishable research result. This file tracks what must become real before the README metrics should be presented as evidence of retrieval quality.

## Current Limits

| Area | Limit | Risk |
| --- | --- | --- |
| Corpus | Built-in, small, partly synthetic engineering corpus. | Results can reflect fixture design instead of general retrieval behavior. |
| Extraction | Deterministic term and edge construction. | Avoids noisy extraction failures that a real graph builder must handle. |
| Embeddings | Local hash fallback by default. | Does not measure semantic embedding quality, cost, or cache behavior. |
| Labels | Generated candidate questions with expected sources. | Ground truth can be circular unless manually audited. |
| Baselines | Local approximations of hybrid, GraphRAG-style, and agentic retrieval. | Comparisons can be directionally useful but not externally convincing. |
| Scale | Tiny graph and 116-question benchmark. | No statistical confidence and limited failure diversity. |

## Upgrade Gates

1. **External corpus gate**
   Add commit-pinned, permissively licensed engineering docs with snapshot manifests and source provenance. Initial targets: Kubernetes KEPs/docs, OpenTelemetry specs, and public architecture/RFC-style documents.

2. **Embedding gate**
   Run the same index through cached API-backed embeddings. Report model name, dimensions, cache hit rate, total tokens, estimated cost, and latency.

3. **Extraction gate**
   Add schema-constrained LLM concept and edge extraction with deterministic caching. Keep the deterministic extractor as a fixture mode for tests.

4. **Golden-label gate**
   Manually audit at least 100 questions. Each row should have expected evidence URIs, expected path labels, negative/distractor notes, and an `audit_status` other than `candidate_needs_human_review`.

5. **Baseline gate**
   Replace or qualify local approximations with stronger baselines: vector-only, BM25+dense hybrid, graph-local traversal, community-summary GraphRAG-style retrieval, bounded agentic search, and layout ablations.

6. **Statistical gate**
   Report confidence intervals by suite: `single_hop`, `multi_hop`, `boundary_crossing`, and stress/failure slices. Include failure taxonomy, not just wins.

## Publishable Claim Bar

Tortus can make a credible public claim only after all of the following are true:

- the corpus is externally sourced and snapshot-reproducible
- embeddings are real semantic embeddings, not only local hash vectors
- extraction failures are measured, not bypassed
- the golden set has human-audited evidence labels
- baselines are either serious implementations or explicitly scoped approximations
- the report includes wins, losses, fanout, latency, cost, and failure analysis

Until then, the honest claim is narrower: Tortus is an executable architecture and evaluation harness for testing whether toroidal, budgeted graph traversal is worth scaling.
