# Evidence Hardening Plan

Tortus currently has a working V2 harness, installable package surface, workspace ingestion, typed diagnostics, and benchmark reports. It is still not a publishable research result. This file tracks what must become real before README metrics should be presented as evidence of broad retrieval quality.

## Current Limits

| Area | Limit | Risk |
| --- | --- | --- |
| Corpus | Built-in engineering corpus plus materialized public Kubernetes, OpenTelemetry, W3C, RFC, SRE, and architecture snapshots. | Results can still reflect fixture design until snapshots are larger and independently reviewed. |
| Extraction | Deterministic term and edge construction. | Avoids noisy extraction failures that a real graph builder must handle. |
| Embeddings | Local hash fallback plus OpenAI and Azure OpenAI adapters with provider-scoped caches. | Does not measure semantic embedding quality unless an API-backed run is reported with model and cost metadata. |
| Labels | Curated candidate questions plus human-audit JSONL import/application. | Ground truth can be circular unless a human maintainer actually reviews evidence spans and path labels. |
| Baselines | Stronger local hybrid graph rerank plus optional GraphRAG, LlamaIndex, and LightRAG command adapters. | Comparisons can be directionally useful but not externally convincing until real external workspaces are configured and reported. |
| Scale | Tiny graph and 118-question benchmark. | Confidence intervals are reported, but failure diversity is still limited. |

## Upgrade Gates

1. **External corpus gate**
   Expand from the packaged public manifest to larger commit-pinned, permissively licensed engineering docs with source provenance. Keep raw SHA256, normalized SHA256, license notes, retrieval timestamps, headers, and extraction warnings.

2. **Embedding gate**
   Run the same index through cached OpenAI or Azure OpenAI embeddings. Report provider, model name, dimensions, cache hit rate, total tokens, estimated cost, and latency.

3. **Extraction gate**
   Add schema-constrained LLM concept and edge extraction with deterministic caching. Keep the deterministic extractor as a fixture mode for tests.

4. **Golden-label gate**
   Manually audit at least 100 questions through `tortus audit export` and `tortus audit import`. Each row should have expected evidence URIs, expected path labels, negative/distractor notes, auditor, reviewed timestamp, and an `audit_status` that reports as `human_reviewed`.

5. **Baseline gate**
   Run and report configured external baselines, starting with Microsoft GraphRAG, LlamaIndex, and LightRAG. Keep local baselines clearly labeled as `_local` controls.

6. **Statistical gate**
   Keep confidence intervals by suite: `single_hop`, `multi_hop`, `boundary_crossing`, and stress/failure slices. Include failure taxonomy, not just wins, and separate audited from unaudited rows.

## Publishable Claim Bar

Tortus can make a credible public claim only after all of the following are true:

- the corpus is externally sourced and snapshot-reproducible
- embeddings are real semantic embeddings, not only local hash vectors
- extraction failures are measured, not bypassed
- the golden set has human-reviewed evidence labels
- baselines are either serious implementations or explicitly scoped approximations
- the report includes wins, losses, fanout, latency, cost, and failure analysis

Until then, the honest claim is narrower: Tortus is an installable architecture, diagnostic workbench, and evaluation harness for testing whether toroidal, budgeted graph traversal is worth scaling.
