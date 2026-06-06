# Tortus: Toroidal Semantic Graph Retrieval

![Tortus dashboard demo](assets/tortus-dashboard-demo.gif)

Tortus is a design-stage retrieval architecture for explainable, multi-hop RAG over large and federated knowledge bases.

The core idea is simple: instead of treating knowledge as a flat set of embedded chunks, Tortus models it as a typed semantic graph embedded onto a soft toroidal manifold. Queries start with vector retrieval, then traverse concept edges, cross domain portals when needed, and return both an answer and the path that produced it.

The bet: topology-aware traversal can improve multi-hop retrieval without turning retrieval into an unbounded agent loop.

> Query concepts, not just chunks. Return reasoning paths, not just citations.

## Status

This repository now contains an executable V2 slice: a Python distribution named `tortus-rag`, an importable `tortus` package, a `tortus` console command, project-local document ingestion, pinned source snapshots, typed graph schemas, SQLite persistence, local embedding fallback, exact vector search, optional FAISS indexing, source-backed answer synthesis, typed retrieval traces, GraphQL plus `/api/query`, a diagnostic dashboard, local and optional external baseline adapters, audit workflows, package/release checks, CI, and reproducible benchmark reports.

The implementation is still early. The intended MVP remains a local prototype that validates whether toroidal graph locality plus typed traversal improves multi-hop retrieval quality, explainability, and shard affinity compared with vector-only RAG, hybrid sparse+dense retrieval, and local approximations of GraphRAG-style and agentic retrieval. The current baselines are useful engineering controls, not claims that Tortus has beaten every external GraphRAG implementation.

Current evidence strength is prototype-level. The benchmark numbers below are useful for checking whether the architecture and evaluation harness behave coherently, but they are not yet a research claim about real-world retrieval superiority.

| Layer | Current state | Evidence implication | Hardening move |
| --- | --- | --- | --- |
| Corpus | Built-in engineering corpus plus source-backed public engineering summaries. | Good for deterministic system tests; still too small and summary-based for external validity. | Add larger commit-pinned public Kubernetes, OpenTelemetry, and architecture/RFC snapshots with manifests. |
| Embeddings | Local hash embedding fallback, with API-backed embedding adapter available. | Validates interfaces and reproducibility; does not prove semantic embedding quality. | Run cached `text-embedding-3-large` or equivalent embeddings and report cost, cache hits, and drift. |
| Extraction | Deterministic term and edge extraction. | Makes tests repeatable; does not test noisy LLM concept extraction. | Add schema-constrained LLM extraction, confidence calibration, retry handling, and human spot checks. |
| Eval labels | 100-question curated set generated from known source patterns, with pending-human-signoff status. | Useful pressure test; not a completed human-reviewed golden set. | Have a human maintainer audit expected evidence URIs, path labels, and negative cases before treating metrics as benchmark results. |
| Baselines | Local vector, BM25, hybrid, graph-local, layout, community-summary, and bounded-agentic approximations. | Good sanity checks; not a final comparison to external systems. | Add serious GraphRAG/RAPTOR/HippoRAG/LightRAG-style implementations or clearly scoped reproductions. |
| Scale | 118 V2 benchmark questions over a 25-node local graph. | Shows mechanics and failure modes; not enough statistical power. | Expand to audited multi-corpus evals with confidence intervals and failure taxonomy by query type. |

## Installation

Tortus is available on PyPI. Install it using `pip`:

```bash
pip install tortus-rag
```

For advanced ingestion (PDF, HTML, URL extraction), install the optional dependencies:
```bash
pip install "tortus-rag[ingest]"
```

## Quickstart

### CLI Usage

Tortus is designed to run locally against your own documentation.

```bash
# 1. Initialize a local Tortus project
tortus init

# 2. Ingest your documents, Markdown files, or URLs
tortus ingest README.md ./docs https://example.com

# 3. Build the graph and vector index
tortus index

# 4. Ask a question and trace the reasoning path
tortus query "What does Tortus say about evidence-backed retrieval?" --explain

# 5. Open the visual graph and query dashboard
tortus serve --port 8010
# Dashboard running at http://localhost:8010
```

### Python API Usage

You can also use Tortus directly in your Python code as a library:

```python
import tortus
from tortus.pipeline import Pipeline

# Initialize the pipeline
pipeline = Pipeline()

# Query the graph
result = pipeline.query("How do service accounts connect to tracing?")

# Print the synthesized answer
print(result.answer)

# Audit the multi-hop reasoning path
for hop in result.reasoning_path:
    print(f"{hop.from_node} --[{hop.edge_type}]--> {hop.to_node}")
```

To run the built-in benchmark corpus:

```bash
.venv/bin/tortus ingest --corpus public-engineering
.venv/bin/tortus index --layout torus --corpus public-engineering
.venv/bin/tortus query "How did the token migration incident connect authentication and tracing?" --explain
.venv/bin/tortus golden-set --out data/golden_set.json --count 100
.venv/bin/tortus eval --suite benchmark --strategies all \
  --json-out data/eval/benchmark.json \
  --duckdb-out data/eval/results.duckdb
.venv/bin/tortus report \
  --eval-json data/eval/benchmark.json \
  --out data/reports/eval-report.md
.venv/bin/tortus serve --port 8010
```

Or run the full local demo path:

```bash
scripts/demo.sh
```

Run checks:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src/tortus scripts/run_pytest.py
.venv/bin/python scripts/run_pytest.py
```

Release checks:

```bash
.venv/bin/python -m build
.venv/bin/twine check dist/*
.venv/bin/tortus release-check
```

Useful configuration:

```bash
TORTUS_CORPUS=public-engineering
TORTUS_EMBEDDING_PROVIDER=local
TORTUS_VECTOR_BACKEND=exact
TORTUS_GRAPHRAG_COMMAND=""
```

`TORTUS_VECTOR_BACKEND=faiss` enables the optional FAISS index path when `faiss` is installed. Exact search remains the default because it is deterministic and easy to test.

`TORTUS_GRAPHRAG_COMMAND` enables the optional `graphrag_external` baseline adapter. If the dependency or command is missing, benchmark reports mark that adapter as skipped rather than counting it as a win.

## User Document Ingestion

Tortus can now run against a local workspace instead of only built-in fixtures:

```bash
tortus init
tortus ingest ./docs
tortus ingest README.md ./docs https://example.com
tortus ingest --manifest sources.toml
tortus index
tortus query "Which docs explain the rollout risk?"
```

Supported local file types are `.md`, `.mdx`, `.txt`, `.html`, `.htm`, and `.pdf`. URL ingestion stores a pinned raw snapshot, normalized text, metadata, SHA256, retrieval timestamp, content type, ETag, Last-Modified, and extraction warnings. HTML extraction uses `trafilatura` with BeautifulSoup fallback; PDF extraction uses `pypdf` and keeps empty/scanned PDFs as warned documents instead of pretending they worked.

Configuration precedence is CLI flags, environment variables, `tortus.toml`, then defaults. After `tortus init`, workspace runtime files live under `.tortus/`.

`scripts/run_pytest.py` exists because some macOS Python builds crash when pytest imports `readline` during startup. It only disables that optional import for pytest.

## Problem

Most production RAG systems are strong at retrieving nearby text and weak at preserving relationships between ideas. That creates recurring failures:

| Failure mode | What happens | Why it matters |
| --- | --- | --- |
| Chunk blindness | The retriever finds relevant fragments but misses the conceptual path between them. | Answers become locally plausible and globally incomplete. |
| Boundary artifacts | Clusters, domains, and shards create artificial edges in the knowledge space. | Cross-domain questions degrade exactly where synthesis is needed most. |
| Weak provenance | Citations point to documents, but not to the reasoning path through concepts. | Users cannot audit why the system connected one fact to another. |
| Prompt-hidden retrieval logic | Traversal policies live inside prompts or app code. | Developers cannot inspect, tune, or constrain retrieval behavior cleanly. |
| Cost drift | Agentic search keeps expanding until a budget or timeout stops it. | Latency and LLM spend become difficult to predict. |

Tortus targets knowledge systems where the answer depends on a path across concepts: engineering design history, policy reasoning, incident analysis, compliance research, product knowledge, and technical support.

![Flat semantic space versus toroidal semantic space](assets/torus-boundary.svg)

Flat partitions create artificial distance; toroidal wrapping preserves neighborhood continuity across boundaries.

## Core Hypothesis

A semantic graph embedded on a toroidal coordinate space can make retrieval more navigable and operationally scalable by combining:

- vector search for fast candidate generation
- typed graph edges for explainable multi-hop traversal
- toroidal locality for wraparound neighborhoods and topology-aware sharding
- GraphQL directives for developer-controlled traversal behavior
- budget-aware LLM synthesis over explicit evidence paths

The torus is not treated as magic. It is a systems hypothesis that should be validated against measurable baselines.

## Non-Goals

Tortus is not trying to be:

- a general replacement for vector databases
- a fully autonomous research agent
- a knowledge graph ontology project
- a prompt-only retrieval strategy
- a claim that toroidal topology is always better than Euclidean or hyperbolic layouts

The goal is narrower: test whether topology-aware semantic graph traversal gives better answers for multi-hop, cross-domain retrieval problems where provenance and cost control matter.

## Why a Torus?

Traditional vector and graph layouts often have boundary effects: points near the edge of a cluster or partition can be artificially far from related concepts. A toroidal space wraps both axes, so neighborhoods do not terminate at hard borders.

In Tortus, toroidal coordinates are used for three concrete jobs:

| Job | Expected benefit | What must be proven |
| --- | --- | --- |
| Neighborhood traversal | Smooth cyclic continuity around dense concept regions. | Better multi-hop recall at equal latency. |
| Sharding | Locality-preserving partitioning without hard semantic edges. | Higher shard affinity and cache hit rate. |
| Federation | Portal hops between overlapping subgraphs without treating every domain boundary as a cliff. | Better cross-domain path quality under budget. |

If the toroidal embedding does not beat simpler layouts in evaluation, it should be replaced. The architecture is designed to make that comparison explicit.

## Competitive Context

Tortus sits between several existing retrieval patterns:

| Pattern | Strength | Limitation Tortus targets |
| --- | --- | --- |
| Vector-only RAG | Fast semantic recall over large corpora. | Weak relationship modeling and shallow provenance. |
| Hybrid sparse+dense retrieval | Strong lexical plus semantic matching. | Still returns ranked items, not concept paths. |
| Knowledge graphs | Explicit relationships and auditability. | Often brittle, expensive to build, and disconnected from embedding-based recall. |
| GraphRAG | Better global summaries and community-level context. | Can blur source-level paths and make query-time control indirect. |
| Agentic search | Flexible multi-step exploration. | Harder to bound, inspect, reproduce, and optimize. |

Tortus attempts to combine the useful parts: fast candidate generation, explicit relationships, bounded traversal, and source-backed answer synthesis.

## What Tortus Beats And Does Not Beat Yet

Current Tortus is strongest when the question needs an auditable path across concepts and domains. It can return source spans, hop types, matched terms, toroidal locality scores, and portal reasons instead of only a ranked list of chunks.

Tortus does **not** yet prove broad superiority over production GraphRAG or agentic retrieval systems. The current GraphRAG-style and bounded-agentic baselines are local approximations that exist to pressure-test the retrieval policy. A publishable claim needs external baseline implementations, larger public corpora, real semantic embeddings, and human-reviewed labels.

| Scenario | Current read |
| --- | --- |
| Single-hop factual retrieval | Vector, BM25, and Tortus can all perform well; Tortus may be extra overhead. |
| Multi-hop incident analysis | Tortus is useful because it exposes the evidence path and portal hops. |
| Boundary-crossing questions | Tortus can help when traversal needs to cross domains under explicit budgets. |
| Unanswerable questions | Tortus now withholds answers when selected evidence has no lexical support. |
| Large-scale production search | Not proven yet; optional FAISS support is the first step, not the endpoint. |

## Failure Examples

The useful failure modes are intentionally visible:

- A query about weather or stock recommendations should return “not enough source-backed evidence” instead of forcing a knowledge path.
- A broad incident query can still over-expand through portals if shared terms are too generic.
- A local-only graph policy can find relevant sources but miss expected boundary-crossing path labels.
- Layout-only probes can retrieve nearby nodes without proving a reasoning path.
- Candidate golden labels remain `curated_pending_human_signoff` until a human maintainer reviews evidence spans.

## Diagnostic Workbench

The installed dashboard is meant to debug retrieval, not just display a pretty graph. A query returns typed diagnostics through GraphQL and the lightweight `/api/query` endpoint:

- seed hits with dense and lexical score components
- selected hops with matched terms, toroidal distance, and reasons
- pruned candidates with prune reasons
- portal decisions and portal budget use
- selected evidence spans
- answer claims and unsupported or weakly supported claims

This is deliberately exposed as product surface because traversal quality is impossible to improve if the rejected candidates and score components disappear inside logs.

## Architecture

```mermaid
flowchart TD
    A[Documents, APIs, tickets, repos] --> B[Ingestion and normalization]
    B --> C[Concept extraction]
    C --> D[Typed semantic graph]
    D --> E[Toroidal coordinate embedding]
    E --> F[ANN index]
    E --> G[Graph store]
    G --> H[Topology-aware shards]

    I[User or LLM query] --> J[Intent parsing]
    J --> K[Top-k vector seeding]
    K --> L[Density-aware graph traversal]
    L --> M[Portal hop planner]
    M --> N[Evidence-constrained synthesis]
    N --> O[Answer plus reasoning path]

    P[GraphQL API] --> J
    P --> L
    P --> M
    P -.-> G
```

## Data Model

Tortus separates semantic content from traversal control.

| Entity | Purpose |
| --- | --- |
| `ConceptNode` | A concept, entity, claim, chunk, document section, API, decision, or event. |
| `SemanticEdge` | A typed relationship such as `supports`, `contradicts`, `depends_on`, `caused_by`, `implements`, or `related_to`. |
| `SubgraphMembership` | Weighted membership in one or more domains, teams, products, sources, or tenants. |
| `PortalEdge` | A controlled cross-subgraph jump used when a query needs domain switching. |
| `EvidenceSpan` | A source-backed span attached to a node or edge for traceability. |
| `TraversalPolicy` | Runtime constraints such as hop budget, latency budget, personalization, freshness, or locality. |

Example node shape:

```json
{
  "id": "concept:llm-bias-evaluation",
  "label": "LLM bias evaluation",
  "kind": "concept",
  "embeddingRef": "emb:9f31",
  "torus": { "theta": 1.84, "phi": 5.12 },
  "memberships": [
    { "subgraph": "ai-governance", "weight": 0.82 },
    { "subgraph": "model-evaluation", "weight": 0.64 }
  ],
  "evidence": [
    { "uri": "docs://eval/bias.md", "span": [120, 184] }
  ]
}
```

## Query API

GraphQL is used as a developer-facing control plane for retrieval. It does not replace the graph store; it gives callers a typed way to constrain traversal.

```graphql
query ExplainConcept($id: ID!) {
  concept(id: $id)
    @semanticGroup(name: "Governance")
    @portalPreference(type: "RecentCaseLaw")
    @failoverPlan(level: 1)
    @explainHops
  {
    id
    label
    confidence
    answer
    reasoningPath {
      from
      to
      edgeType
      weight
      evidence {
        uri
        span
      }
    }
  }
}
```

Planned directives:

| Directive | Purpose |
| --- | --- |
| `@semanticGroup(name: String!)` | Prefer a domain-specific subgraph. |
| `@portalPreference(type: String!)` | Bias cross-subgraph portal selection. |
| `@failoverPlan(level: Int!)` | Allow bounded retries or partial answers. |
| `@explainHops` | Return the traversal path and evidence spans. |
| `@noPersonalization` | Disable user-context personalization. |
| `@localOnly` | Prevent portal hops outside the selected subgraph. |
| `@budget(maxHops: Int, maxMs: Int, maxTokens: Int)` | Bound latency, depth, and LLM cost. |

## Retrieval Algorithm

At query time, Tortus follows a bounded retrieval plan:

1. Parse query intent, constraints, and GraphQL directives.
2. Generate seed candidates with ANN vector search.
3. Map candidates to graph nodes and toroidal coordinates.
4. Estimate local density around each seed.
5. Expand through typed edges using a density-aware radius.
6. Score frontier nodes with semantic similarity, edge weight, freshness, evidence quality, and policy constraints.
7. Trigger portal hops when the frontier has low coverage or the query implies domain switching.
8. Select evidence paths under hop, latency, and token budgets.
9. Synthesize an answer only from selected evidence.
10. Return the answer, confidence, path, and degraded-mode warnings when applicable.

Traversal score sketch:

```text
score(next) =
  semantic_similarity(query, next)
  + edge_weight(current, next)
  + evidence_quality(next)
  + freshness_bias(next)
  - traversal_cost(next)
  - uncertainty_penalty(next)
```

The exact scoring function is intentionally replaceable. The MVP should make retrieval policies easy to compare rather than hard-coding one strategy.

## Evaluation Plan

Tortus should be judged by evidence, not novelty language.

| Dimension | Metrics |
| --- | --- |
| Retrieval quality | recall@k, multi-hop path recall, answer faithfulness, contradiction rate |
| Path quality | hop precision, evidence coverage, path minimality, human audit score |
| System performance | p50/p95 latency, shard fanout, cache hit rate, index update cost |
| Cost control | tokens per answered query, LLM calls per query, timeout rate |
| Federation | cross-subgraph success rate, partial-answer quality, failover rate |

Current V2 eval strategies:

- `tortus_torus`
- `vector_only_local`
- `bm25_local`
- `hybrid_dense_bm25_local`
- `graph_local`
- `community_summary_local`
- `bounded_agentic_local`
- `torus_layout_local`
- `euclidean_layout_local`
- `random_layout_local`
- `graphrag_external` when optional dependency and command configuration are present

The older unqualified strategy names remain accepted as CLI aliases and map to the `_local` strategies.

Current V2 benchmark, using `tortus eval --suite benchmark --strategies all` over 118 questions and 1,180 strategy rows. A pass requires term recall >= 0.50, source recall >= 0.50, path recall >= 0.50, and faithfulness >= 0.50 for answerable questions. Negative questions pass only when unsupported answers are withheld:

| Strategy | Pass | Source | Path | Precision | Faith | p95 ms | Portals | Fanout |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `tortus_torus` | 0.77 | 0.72 | 1.00 | 0.64 | 0.88 | 4.9 | 3.5 | 5.2 |
| `bounded_agentic_local` | 0.64 | 0.63 | 0.95 | 0.86 | 0.89 | 3.3 | 3.0 | 4.4 |
| `graph_local` | 0.14 | 0.57 | 0.17 | 0.34 | 0.88 | 2.5 | 0.0 | 4.3 |
| `bm25_local` | 0.02 | 0.63 | 0.03 | 0.03 | 0.88 | 1.1 | 0.0 | 4.2 |
| `community_summary_local` | 0.02 | 0.49 | 0.03 | 0.03 | 0.88 | 1.1 | 0.0 | 4.1 |
| `hybrid_dense_bm25_local` | 0.01 | 0.69 | 0.03 | 0.03 | 0.88 | 2.1 | 0.0 | 4.4 |
| `vector_only_local` | 0.01 | 0.68 | 0.03 | 0.03 | 0.88 | 0.9 | 0.0 | 4.3 |
| `torus_layout_local` | 0.01 | 0.51 | 0.03 | 0.03 | 0.88 | 1.0 | 0.0 | 3.1 |
| `euclidean_layout_local` | 0.01 | 0.45 | 0.03 | 0.03 | 0.89 | 0.9 | 0.0 | 3.1 |
| `random_layout_local` | 0.00 | 0.22 | 0.03 | 0.03 | 0.89 | 0.9 | 0.0 | 4.3 |

The positive signal is full benchmark path recall with improved selectivity: Tortus now clears the V2 targets of pass >= 0.70, path recall >= 0.90, path precision >= 0.60, mean fanout <= 5.5, and mean portal hops <= 5.0. The remaining caveat is external validity: because the corpus, extraction, embeddings, and labels are still controlled fixtures or source-backed summaries, this table should be read as a V2 harness result, not as proof that toroidal retrieval beats production systems.

The `data/golden_set.json` file is a deterministic 100-question curated golden set with expected evidence URIs and hop targets. Its `audit_status` is intentionally `curated_pending_human_signoff`; it is ready for maintainer review, not presented as a completed externally reviewed benchmark.

Remaining work for a publishable external result:

- replace or supplement local approximations with external GraphRAG and agentic-search implementations
- scale beyond source-backed summaries to larger commit-pinned public engineering snapshots
- have a human maintainer audit and sign off the 100-question curated golden set
- profile real API-backed embedding and synthesis cost

The project is successful only if it can show a measurable improvement for questions that require concept paths, while staying competitive on latency and cost.

## MVP Scope

The first implementation should be small enough to finish and rigorous enough to learn from.

| Phase | Deliverable |
| --- | --- |
| 0 | Finalize schema, traversal interfaces, and evaluation dataset. |
| 1 | Build a local graph index over a small technical-document corpus. |
| 2 | Add toroidal coordinates, ANN seeding, and typed edge traversal. |
| 3 | Expose GraphQL query directives and reasoning-path responses. |
| 4 | Run baseline comparisons and publish results. |
| 5 | Add portal hops and topology-aware sharding if earlier phases justify them. |

Current repository shape:

```text
src/
  tortus/
    config.py       project config, environment precedence, and settings helpers
    corpus.py       built-in engineering/public corpora and chunking
    corpus_manifest.py pinned public corpus manifest fetch/verify workflows
    ingest.py       workspace file, URL, HTML, and PDF snapshot ingestion
    extract.py      deterministic source-aware concept and edge extraction
    text.py         shared tokenization, phrase, and sentence utilities
    embeddings.py   local and Azure OpenAI embedding adapters
    graph_store.py  SQLite graph persistence
    torus.py        toroidal distance and projection
    traversal.py    bounded path retrieval and extractive synthesis
    vector.py       exact vector index plus optional FAISS backend
    baselines.py    local baseline runners and optional external adapter protocol
    sharding.py     toroidal shard assignment and crossing metrics
    golden.py       deterministic curated golden-set generation
    audit.py        human audit export/import workflows
    api.py          FastAPI, GraphQL, and dashboard routes
    eval.py         smoke/golden/stress/negative/full/benchmark evaluation harness
    eval_store.py   JSON and DuckDB eval persistence
    report.py       benchmark markdown report and failure taxonomy
    release.py      doctor and release-check helpers
    cli.py          init/ingest/index/query/serve/corpus/audit/eval/report/release commands
    resources/      packaged manifests and runtime resources
    templates/      Jinja dashboard shell
    static/         Plotly dashboard JavaScript and CSS
data/
  golden_set.json   100-question curated golden set requiring maintainer signoff
  benchmark_snapshots/
    smoke_thresholds.json
  reports/
    eval-report.md  generated benchmark report
docs/
  adr/               short architecture decision records
  evidence-hardening.md  gates from V2 harness to credible external benchmark
scripts/
  demo.sh           rebuild, query, evaluate, and report
  run_pytest.py     pytest startup wrapper for local macOS stability
tests/
  test_*.py
```

## Design Principles

- Make retrieval inspectable before making it clever.
- Treat LLMs as synthesis and policy helpers, not as hidden databases.
- Return evidence paths for claims that cross concepts.
- Put budgets in the API, not only in deployment config.
- Prefer replaceable retrieval policies over one monolithic agent loop.
- Measure against boring baselines before adding exotic machinery.

## Potential Use Cases

| Domain | Example |
| --- | --- |
| Engineering knowledge | Trace why an API, architecture decision, or reliability pattern changed over time. |
| Support policy reasoning | Connect customer symptoms, policy rules, exceptions, and historical resolutions. |
| Compliance and governance | Traverse regulation, internal controls, audits, and model behavior evidence. |
| Research synthesis | Connect papers, claims, datasets, contradictions, and follow-up questions. |
| Private knowledge assistants | Run local or tenant-scoped concept traversal with explicit privacy controls. |

## Risks and Open Questions

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Toroidal layout may not outperform simpler embeddings. | The central topology claim needs proof. | Keep layout pluggable and run direct ablations. |
| Concept extraction can create noisy nodes and edges. | Bad graph structure harms traversal quality. | Track edge provenance and confidence; support pruning. |
| LLM-guided traversal may overfit to plausible paths. | Explanations can become narrative instead of evidence. | Require evidence spans for returned hops. |
| GraphQL directives can become too complex. | Developer ergonomics matter for adoption. | Start with a minimal directive set and add only measured needs. |
| Federation can increase latency. | Cross-domain search is expensive. | Enforce hop, shard, time, and token budgets at query time. |

## Research Extensions

- learned edge traversal policies
- contrastive refinement of graph and toroidal embeddings
- path-aware reranking
- visual graph debugger for retrieval traces
- self-healing schema federation
- privacy-preserving local subgraphs

## What I Learned

- Path recall is the real differentiator: vector, BM25, and hybrid retrieval can find terms and nearby sources, but they do not naturally return auditable multi-hop evidence paths.
- V2 reduced mean fanout from the earlier broad traversal while keeping full benchmark path recall. The next algorithmic target is making this selectivity hold on larger, noisier user corpora.
- The bounded-agentic baseline is strong enough to keep in the benchmark. Tortus has to justify itself with provenance, reproducibility, and predictable budgets, not only raw recall.
- Curated golden sets are useful for pressure testing, but the numbers should not be treated as research claims until a human maintainer signs off the evidence labels.

## Author

Created by Darsh Garg.

- GitHub: `darshgarg7`
- Email: `darsh.garg@gmail.com`

## License

MIT. Use freely for educational, research, and portfolio purposes.
