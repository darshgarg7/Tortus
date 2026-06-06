# Tortus Evaluation Report

Suite: `benchmark`. Rows: `1652`. A pass requires term recall >= 0.50, source recall >= 0.50, path recall >= 0.50, and faithfulness >= 0.50 for answerable questions. Negative questions pass only when unsupported answers are withheld. Skipped external adapters are reported separately and are not counted as wins. This is a local v2 benchmark, not a production superiority claim.

## Strategy Summary

| strategy | rows | pass | 95% CI | term | source | path | precision | faith | p50 ms | p95 ms | nodes | portals | fanout | cross | warn | skipped |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25_local | 118 | 0.02 | 0.00-0.04 | 1.00 | 0.65 | 0.03 | 0.03 | 0.88 | 0.9 | 1.0 | 5.0 | 0.0 | 4.2 | 0.0 | 0.01 | 0.00 |
| bounded_agentic_local | 118 | 0.73 | 0.65-0.81 | 0.99 | 0.67 | 0.95 | 0.86 | 0.89 | 2.4 | 3.0 | 5.7 | 3.0 | 4.4 | 3.7 | 0.00 | 0.00 |
| community_summary_local | 118 | 0.02 | 0.00-0.04 | 0.97 | 0.52 | 0.03 | 0.03 | 0.88 | 0.9 | 1.0 | 4.9 | 0.0 | 4.1 | 0.0 | 0.01 | 0.00 |
| euclidean_layout_local | 118 | 0.01 | 0.00-0.03 | 0.87 | 0.52 | 0.03 | 0.03 | 0.89 | 0.7 | 0.8 | 5.0 | 0.0 | 3.1 | 0.0 | 0.00 | 0.00 |
| graph_local | 118 | 0.14 | 0.08-0.21 | 0.96 | 0.58 | 0.17 | 0.34 | 0.88 | 1.5 | 2.2 | 5.8 | 0.0 | 4.3 | 4.2 | 0.02 | 0.00 |
| graphrag_external | 118 | 0.00 | 0.00-0.00 | 0.02 | 0.02 | 0.03 | 0.03 | 0.02 | 0.1 | 0.1 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 1.00 |
| hybrid_dense_bm25_local | 118 | 0.01 | 0.00-0.03 | 0.97 | 0.73 | 0.03 | 0.03 | 0.88 | 1.4 | 1.5 | 5.0 | 0.0 | 4.4 | 0.0 | 0.00 | 0.00 |
| hybrid_graph_rerank_local | 118 | 0.80 | 0.72-0.87 | 0.99 | 0.74 | 1.00 | 0.82 | 0.88 | 4.8 | 5.7 | 14.6 | 27.9 | 8.8 | 30.3 | 0.00 | 0.00 |
| lightrag_external | 118 | 0.00 | 0.00-0.00 | 0.02 | 0.02 | 0.03 | 0.03 | 0.02 | 0.1 | 0.1 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 1.00 |
| llamaindex_external | 118 | 0.01 | 0.00-0.03 | 0.95 | 0.72 | 0.03 | 0.03 | 0.88 | 7.1 | 7.5 | 5.0 | 0.0 | 4.3 | 0.0 | 0.00 | 0.00 |
| random_layout_local | 118 | 0.01 | 0.00-0.03 | 0.79 | 0.32 | 0.03 | 0.03 | 0.89 | 0.7 | 0.8 | 5.0 | 0.0 | 4.3 | 0.0 | 0.00 | 0.00 |
| tortus_torus | 118 | 0.80 | 0.72-0.87 | 1.00 | 0.73 | 1.00 | 0.64 | 0.88 | 2.4 | 3.4 | 7.0 | 3.5 | 5.2 | 5.6 | 0.02 | 0.00 |
| torus_layout_local | 118 | 0.01 | 0.00-0.03 | 0.88 | 0.58 | 0.03 | 0.03 | 0.88 | 0.8 | 1.0 | 5.0 | 0.0 | 3.1 | 0.0 | 0.00 | 0.00 |
| vector_only_local | 118 | 0.01 | 0.00-0.03 | 0.96 | 0.71 | 0.03 | 0.03 | 0.88 | 0.7 | 0.8 | 5.0 | 0.0 | 4.3 | 0.0 | 0.00 | 0.00 |

## Thesis Check

v2 is inconclusive on pass rate: `tortus_torus` is +0.00 pass-rate points, -0.01 source-recall points, and +0.00 path-recall points, and -0.00 faithfulness points versus the strongest current baseline (`hybrid_graph_rerank_local`).

## Suite Breakdown

| suite | strategy | pass | source | path | precision | faith | p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| boundary_crossing | bm25_local | 0.00 | 0.61 | 0.00 | 0.00 | 0.89 | 0.9 |
| boundary_crossing | bounded_agentic_local | 1.00 | 0.72 | 1.00 | 0.87 | 0.89 | 2.8 |
| boundary_crossing | community_summary_local | 0.00 | 0.61 | 0.00 | 0.00 | 0.88 | 1.3 |
| boundary_crossing | euclidean_layout_local | 0.00 | 0.39 | 0.00 | 0.00 | 0.88 | 0.9 |
| boundary_crossing | graph_local | 0.00 | 0.50 | 0.00 | 0.21 | 0.88 | 1.7 |
| boundary_crossing | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| boundary_crossing | hybrid_dense_bm25_local | 0.00 | 0.83 | 0.00 | 0.00 | 0.88 | 1.4 |
| boundary_crossing | hybrid_graph_rerank_local | 1.00 | 0.83 | 1.00 | 0.85 | 0.88 | 5.8 |
| boundary_crossing | lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| boundary_crossing | llamaindex_external | 0.00 | 0.50 | 0.00 | 0.00 | 0.88 | 6.1 |
| boundary_crossing | random_layout_local | 0.00 | 0.22 | 0.00 | 0.00 | 0.89 | 0.7 |
| boundary_crossing | tortus_torus | 1.00 | 0.72 | 1.00 | 0.71 | 0.88 | 2.7 |
| boundary_crossing | torus_layout_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.87 | 35.2 |
| boundary_crossing | vector_only_local | 0.00 | 0.50 | 0.00 | 0.00 | 0.88 | 0.6 |
| golden_candidate | bm25_local | 0.00 | 0.64 | 0.00 | 0.00 | 0.88 | 1.0 |
| golden_candidate | bounded_agentic_local | 0.73 | 0.67 | 0.95 | 0.88 | 0.89 | 3.0 |
| golden_candidate | community_summary_local | 0.00 | 0.51 | 0.00 | 0.00 | 0.88 | 1.0 |
| golden_candidate | euclidean_layout_local | 0.00 | 0.53 | 0.00 | 0.00 | 0.89 | 0.8 |
| golden_candidate | graph_local | 0.12 | 0.57 | 0.15 | 0.34 | 0.88 | 2.3 |
| golden_candidate | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| golden_candidate | hybrid_dense_bm25_local | 0.00 | 0.73 | 0.00 | 0.00 | 0.88 | 1.5 |
| golden_candidate | hybrid_graph_rerank_local | 0.81 | 0.74 | 0.99 | 0.84 | 0.88 | 5.7 |
| golden_candidate | lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| golden_candidate | llamaindex_external | 0.00 | 0.73 | 0.00 | 0.00 | 0.88 | 7.5 |
| golden_candidate | random_layout_local | 0.00 | 0.33 | 0.00 | 0.00 | 0.89 | 0.8 |
| golden_candidate | tortus_torus | 0.79 | 0.72 | 1.00 | 0.65 | 0.88 | 3.4 |
| golden_candidate | torus_layout_local | 0.00 | 0.58 | 0.00 | 0.00 | 0.88 | 0.9 |
| golden_candidate | vector_only_local | 0.00 | 0.73 | 0.00 | 0.00 | 0.88 | 0.8 |
| multi_hop | bm25_local | 0.00 | 0.78 | 0.00 | 0.00 | 0.88 | 0.8 |
| multi_hop | bounded_agentic_local | 0.67 | 0.78 | 0.83 | 0.87 | 0.89 | 2.7 |
| multi_hop | community_summary_local | 0.00 | 0.44 | 0.00 | 0.00 | 0.88 | 1.4 |
| multi_hop | euclidean_layout_local | 0.00 | 0.56 | 0.00 | 0.00 | 0.89 | 0.8 |
| multi_hop | graph_local | 0.00 | 0.56 | 0.17 | 0.42 | 0.86 | 2.1 |
| multi_hop | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| multi_hop | hybrid_dense_bm25_local | 0.00 | 0.78 | 0.00 | 0.00 | 0.88 | 1.4 |
| multi_hop | hybrid_graph_rerank_local | 0.67 | 0.78 | 1.00 | 0.93 | 0.88 | 4.5 |
| multi_hop | lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| multi_hop | llamaindex_external | 0.00 | 0.67 | 0.00 | 0.00 | 0.89 | 7.3 |
| multi_hop | random_layout_local | 0.00 | 0.33 | 0.00 | 0.00 | 0.89 | 0.9 |
| multi_hop | tortus_torus | 0.67 | 0.67 | 1.00 | 0.81 | 0.88 | 2.0 |
| multi_hop | torus_layout_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.89 | 6.2 |
| multi_hop | vector_only_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.88 | 0.6 |
| negative | bm25_local | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 | 0.7 |
| negative | bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 2.6 |
| negative | community_summary_local | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 | 0.7 |
| negative | euclidean_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.5 |
| negative | graph_local | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 1.9 |
| negative | graphrag_external | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.1 |
| negative | hybrid_dense_bm25_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.1 |
| negative | hybrid_graph_rerank_local | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 4.4 |
| negative | lightrag_external | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.1 |
| negative | llamaindex_external | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 6.9 |
| negative | random_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.5 |
| negative | tortus_torus | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 3.4 |
| negative | torus_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.1 |
| negative | vector_only_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.5 |
| single_hop | bm25_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.83 | 0.9 |
| single_hop | bounded_agentic_local | 1.00 | 1.00 | 1.00 | 0.25 | 0.85 | 1.4 |
| single_hop | community_summary_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.86 | 0.8 |
| single_hop | euclidean_layout_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.85 | 0.6 |
| single_hop | graph_local | 1.00 | 1.00 | 1.00 | 0.12 | 0.85 | 1.6 |
| single_hop | graphrag_external | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.1 |
| single_hop | hybrid_dense_bm25_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.87 | 1.2 |
| single_hop | hybrid_graph_rerank_local | 1.00 | 1.00 | 1.00 | 0.03 | 0.87 | 3.9 |
| single_hop | lightrag_external | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.1 |
| single_hop | llamaindex_external | 1.00 | 1.00 | 1.00 | 1.00 | 0.87 | 604.1 |
| single_hop | random_layout_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.88 | 0.7 |
| single_hop | tortus_torus | 1.00 | 1.00 | 1.00 | 0.17 | 0.85 | 4.1 |
| single_hop | torus_layout_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.85 | 0.7 |
| single_hop | vector_only_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.87 | 0.6 |
| stress | bm25_local | 0.00 | 0.78 | 0.00 | 0.00 | 0.88 | 1.1 |
| stress | bounded_agentic_local | 0.78 | 0.78 | 0.94 | 0.93 | 0.88 | 2.8 |
| stress | community_summary_local | 0.00 | 0.48 | 0.00 | 0.00 | 0.88 | 1.0 |
| stress | euclidean_layout_local | 0.00 | 0.52 | 0.00 | 0.00 | 0.88 | 0.8 |
| stress | graph_local | 0.22 | 0.63 | 0.17 | 0.38 | 0.87 | 1.6 |
| stress | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| stress | hybrid_dense_bm25_local | 0.00 | 0.78 | 0.00 | 0.00 | 0.88 | 1.6 |
| stress | hybrid_graph_rerank_local | 0.78 | 0.81 | 1.00 | 0.84 | 0.88 | 5.2 |
| stress | lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| stress | llamaindex_external | 0.00 | 0.78 | 0.00 | 0.00 | 0.88 | 7.4 |
| stress | random_layout_local | 0.00 | 0.28 | 0.00 | 0.00 | 0.88 | 0.7 |
| stress | tortus_torus | 0.78 | 0.78 | 1.00 | 0.69 | 0.88 | 2.7 |
| stress | torus_layout_local | 0.00 | 0.59 | 0.00 | 0.00 | 0.88 | 0.9 |
| stress | vector_only_local | 0.00 | 0.78 | 0.00 | 0.00 | 0.88 | 0.8 |

## Audit Status

| audit status | rows |
| --- | --- |
| assistant_reviewed | 1400 |
| built_in | 252 |

## External Baselines

External rows: `354`. Skipped rows: `236`.

| category | count |
| --- | --- |
| microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. | 118 |
| lightrag external baseline skipped: set TORTUS_LIGHTRAG_COMMAND to a command template containing {query}. | 118 |

## Boundary-Crossing Slice

| strategy | pass | source | path | precision | faith | portals | fanout | cross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25_local | 0.00 | 0.61 | 0.00 | 0.00 | 0.89 | 0.0 | 4.0 | 0.0 |
| bounded_agentic_local | 1.00 | 0.72 | 1.00 | 0.87 | 0.89 | 3.0 | 5.0 | 3.3 |
| community_summary_local | 0.00 | 0.61 | 0.00 | 0.00 | 0.88 | 0.0 | 3.7 | 0.0 |
| euclidean_layout_local | 0.00 | 0.39 | 0.00 | 0.00 | 0.88 | 0.0 | 2.7 | 0.0 |
| graph_local | 0.00 | 0.50 | 0.00 | 0.21 | 0.88 | 0.0 | 4.0 | 3.7 |
| graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 | 0.0 | 0.0 |
| hybrid_dense_bm25_local | 0.00 | 0.83 | 0.00 | 0.00 | 0.88 | 0.0 | 3.7 | 0.0 |
| hybrid_graph_rerank_local | 1.00 | 0.83 | 1.00 | 0.85 | 0.88 | 29.7 | 10.0 | 31.3 |
| lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 | 0.0 | 0.0 |
| llamaindex_external | 0.00 | 0.50 | 0.00 | 0.00 | 0.88 | 0.0 | 3.3 | 0.0 |
| random_layout_local | 0.00 | 0.22 | 0.00 | 0.00 | 0.89 | 0.0 | 4.7 | 0.0 |
| tortus_torus | 1.00 | 0.72 | 1.00 | 0.71 | 0.88 | 4.7 | 5.7 | 6.0 |
| torus_layout_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.87 | 0.0 | 3.3 | 0.0 |
| vector_only_local | 0.00 | 0.50 | 0.00 | 0.00 | 0.88 | 0.0 | 3.3 | 0.0 |

## Failure Taxonomy

| category | count |
| --- | --- |
| missing_expected_path | 1242 |
| missing_expected_sources | 319 |
| missing_expected_terms | 234 |
| low_faithfulness | 232 |
| low_path_precision | 90 |
| high_shard_fanout | 42 |
| warning_only | 5 |
| candidate_generation_miss | 1 |

## Cost And Fanout Notes

Highest mean shard fanout: `hybrid_graph_rerank_local` (8.8). Highest p95 latency: `llamaindex_external` (7.5 ms). Highest warning rate: `graphrag_external` (1.00). The V2 selectivity target is path recall >= 0.90, path precision >= 0.60, mean fanout <= 5.5, and mean portal hops <= 5.0.

## Hardest Misses

| question | strategy | term | source | path | precision | faith | warnings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| boundary-crossing-observability | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. |
| golden-auth-trace-runbook | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. |
| golden-distractor-token-cache | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. |
| golden-legacy-secret-distractor | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. |
| golden-sidecar-not-root-cause | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. |
| golden100-001-auth-trace-incident | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. |
| golden100-002-audience-dashboard | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. |
| golden100-003-token-projection-rollout | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. |

## Reproduction

```bash
tortus ingest --corpus public-engineering --data-dir data
tortus index --layout torus --corpus public-engineering --data-dir data
tortus golden-set --out data/golden_set.json --count 100
tortus eval --suite benchmark --strategies all_with_external \
  --corpus public-engineering \
  --data-dir data \
  --audit-file data/audits/golden100.codex-reviewed.jsonl \
  --json-out data/eval/benchmark.json \
  --duckdb-out data/eval/results.duckdb
tortus report --eval-json data/eval/benchmark.json --out data/reports/eval-report.md
```
