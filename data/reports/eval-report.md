# Tortus Evaluation Report

Suite: `benchmark`. Rows: `1652`. A pass requires term recall >= 0.50, source recall >= 0.50, path recall >= 0.50, and faithfulness >= 0.50 for answerable questions. Negative questions pass only when unsupported answers are withheld. Skipped external adapters are reported separately and are not counted as wins. This is a local v2 benchmark, not a production superiority claim.

## Strategy Summary

| strategy | rows | pass | 95% CI | term | source | path | precision | faith | p50 ms | p95 ms | nodes | portals | fanout | cross | warn | skipped |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25_local | 118 | 0.00 | 0.00-0.00 | 0.34 | 0.00 | 0.03 | 0.03 | 0.92 | 3.1 | 4.2 | 5.0 | 0.0 | 3.8 | 0.0 | 0.00 | 0.00 |
| bounded_agentic_local | 118 | 0.00 | 0.00-0.00 | 0.32 | 0.00 | 1.00 | 0.37 | 0.84 | 6.2 | 7.9 | 11.9 | 2.9 | 5.8 | 8.2 | 0.04 | 0.00 |
| community_summary_local | 118 | 0.00 | 0.00-0.00 | 0.34 | 0.00 | 0.03 | 0.03 | 0.92 | 3.7 | 4.3 | 4.9 | 0.0 | 4.1 | 0.0 | 0.00 | 0.00 |
| euclidean_layout_local | 118 | 0.00 | 0.00-0.00 | 0.12 | 0.00 | 0.03 | 0.03 | 0.71 | 2.1 | 2.8 | 5.0 | 0.0 | 1.4 | 0.0 | 0.00 | 0.00 |
| graph_local | 118 | 0.02 | 0.00-0.04 | 0.26 | 0.02 | 0.17 | 0.14 | 0.87 | 3.3 | 6.3 | 11.3 | 0.0 | 4.5 | 4.7 | 0.02 | 0.00 |
| graphrag_external | 118 | 0.00 | 0.00-0.00 | 0.02 | 0.02 | 0.03 | 0.03 | 0.02 | 0.1 | 0.1 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 1.00 |
| hybrid_dense_bm25_local | 118 | 0.00 | 0.00-0.00 | 0.32 | 0.00 | 0.03 | 0.03 | 0.93 | 5.0 | 5.9 | 5.0 | 0.0 | 3.6 | 0.0 | 0.00 | 0.00 |
| hybrid_graph_rerank_local | 118 | 0.00 | 0.00-0.00 | 0.30 | 0.00 | 1.00 | 0.52 | 0.92 | 9.2 | 10.7 | 35.8 | 14.3 | 8.9 | 22.6 | 0.00 | 0.00 |
| lightrag_external | 118 | 0.00 | 0.00-0.00 | 0.02 | 0.02 | 0.03 | 0.03 | 0.02 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 1.00 |
| llamaindex_external | 118 | 0.00 | 0.00-0.00 | 0.02 | 0.02 | 0.03 | 0.03 | 0.02 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.00 | 1.00 |
| random_layout_local | 118 | 0.00 | 0.00-0.00 | 0.11 | 0.00 | 0.03 | 0.03 | 0.66 | 2.1 | 2.8 | 5.0 | 0.0 | 3.5 | 0.0 | 0.00 | 0.00 |
| tortus_torus | 118 | 0.02 | 0.00-0.04 | 0.27 | 0.02 | 0.67 | 0.22 | 0.88 | 3.9 | 8.5 | 11.0 | 0.8 | 4.5 | 4.7 | 0.02 | 0.00 |
| torus_layout_local | 118 | 0.00 | 0.00-0.00 | 0.12 | 0.00 | 0.03 | 0.03 | 0.71 | 2.3 | 2.8 | 5.0 | 0.0 | 1.4 | 0.0 | 0.00 | 0.00 |
| vector_only_local | 118 | 0.00 | 0.00-0.00 | 0.16 | 0.00 | 0.03 | 0.03 | 0.83 | 1.4 | 1.8 | 5.0 | 0.0 | 2.9 | 0.0 | 0.00 | 0.00 |

## Thesis Check

v2 is inconclusive on pass rate: `tortus_torus` is +0.00 pass-rate points, +0.00 source-recall points, and +0.50 path-recall points, and +0.01 faithfulness points versus the strongest current baseline (`graph_local`).

## Suite Breakdown

| suite | strategy | pass | source | path | precision | faith | p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| boundary_crossing | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.91 | 3.2 |
| boundary_crossing | bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.29 | 0.85 | 6.8 |
| boundary_crossing | community_summary_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.89 | 3.9 |
| boundary_crossing | euclidean_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.28 | 2.5 |
| boundary_crossing | graph_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.71 | 4.2 |
| boundary_crossing | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| boundary_crossing | hybrid_dense_bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 | 5.6 |
| boundary_crossing | hybrid_graph_rerank_local | 0.00 | 0.00 | 1.00 | 0.48 | 0.91 | 10.3 |
| boundary_crossing | lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 |
| boundary_crossing | llamaindex_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 |
| boundary_crossing | random_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.30 | 2.5 |
| boundary_crossing | tortus_torus | 0.00 | 0.00 | 0.33 | 0.04 | 0.76 | 5.4 |
| boundary_crossing | torus_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.28 | 2.3 |
| boundary_crossing | vector_only_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.85 | 1.6 |
| golden_candidate | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 | 4.0 |
| golden_candidate | bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.37 | 0.83 | 7.9 |
| golden_candidate | community_summary_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 | 4.3 |
| golden_candidate | euclidean_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.77 | 2.8 |
| golden_candidate | graph_local | 0.00 | 0.00 | 0.15 | 0.15 | 0.89 | 6.2 |
| golden_candidate | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| golden_candidate | hybrid_dense_bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.93 | 5.9 |
| golden_candidate | hybrid_graph_rerank_local | 0.00 | 0.00 | 0.99 | 0.53 | 0.92 | 10.7 |
| golden_candidate | lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 |
| golden_candidate | llamaindex_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 |
| golden_candidate | random_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.70 | 2.8 |
| golden_candidate | tortus_torus | 0.00 | 0.00 | 0.65 | 0.23 | 0.89 | 6.5 |
| golden_candidate | torus_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.77 | 2.8 |
| golden_candidate | vector_only_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.87 | 1.8 |
| multi_hop | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.91 | 32.0 |
| multi_hop | bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.54 | 0.86 | 8.5 |
| multi_hop | community_summary_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 | 4.0 |
| multi_hop | euclidean_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.29 | 2.7 |
| multi_hop | graph_local | 0.00 | 0.00 | 0.17 | 0.21 | 0.77 | 5.7 |
| multi_hop | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| multi_hop | hybrid_dense_bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 | 5.9 |
| multi_hop | hybrid_graph_rerank_local | 0.00 | 0.00 | 1.00 | 0.66 | 0.91 | 10.6 |
| multi_hop | lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 |
| multi_hop | llamaindex_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 |
| multi_hop | random_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 33.1 |
| multi_hop | tortus_torus | 0.00 | 0.00 | 1.00 | 0.26 | 0.84 | 4.1 |
| multi_hop | torus_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.29 | 2.6 |
| multi_hop | vector_only_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.29 | 1.7 |
| negative | bm25_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 3.0 |
| negative | bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 7.1 |
| negative | community_summary_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 3.7 |
| negative | euclidean_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 2.4 |
| negative | graph_local | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 5.4 |
| negative | graphrag_external | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.1 |
| negative | hybrid_dense_bm25_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 5.1 |
| negative | hybrid_graph_rerank_local | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 8.3 |
| negative | lightrag_external | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0 |
| negative | llamaindex_external | 0.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.0 |
| negative | random_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 39.1 |
| negative | tortus_torus | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 9.5 |
| negative | torus_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 2.4 |
| negative | vector_only_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.4 |
| single_hop | bm25_local | 0.00 | 0.00 | 1.00 | 1.00 | 0.93 | 3.1 |
| single_hop | bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.00 | 0.87 | 6.0 |
| single_hop | community_summary_local | 0.00 | 0.00 | 1.00 | 1.00 | 0.92 | 3.7 |
| single_hop | euclidean_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.9 |
| single_hop | graph_local | 0.00 | 0.00 | 1.00 | 0.00 | 0.46 | 5.1 |
| single_hop | graphrag_external | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.1 |
| single_hop | hybrid_dense_bm25_local | 0.00 | 0.00 | 1.00 | 1.00 | 0.92 | 5.2 |
| single_hop | hybrid_graph_rerank_local | 0.00 | 0.00 | 1.00 | 0.00 | 0.92 | 9.4 |
| single_hop | lightrag_external | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.0 |
| single_hop | llamaindex_external | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 0.0 |
| single_hop | random_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 2.0 |
| single_hop | tortus_torus | 0.00 | 0.00 | 1.00 | 0.00 | 0.59 | 11.2 |
| single_hop | torus_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 2.2 |
| single_hop | vector_only_local | 0.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.8 |
| stress | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 | 3.9 |
| stress | bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.46 | 0.84 | 7.5 |
| stress | community_summary_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 | 4.2 |
| stress | euclidean_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.39 | 2.7 |
| stress | graph_local | 0.00 | 0.00 | 0.17 | 0.15 | 0.83 | 6.7 |
| stress | graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.1 |
| stress | hybrid_dense_bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.91 | 5.9 |
| stress | hybrid_graph_rerank_local | 0.00 | 0.00 | 1.00 | 0.63 | 0.90 | 32.5 |
| stress | lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 |
| stress | llamaindex_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 |
| stress | random_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.59 | 2.7 |
| stress | tortus_torus | 0.00 | 0.00 | 0.78 | 0.25 | 0.86 | 29.3 |
| stress | torus_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.39 | 2.6 |
| stress | vector_only_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.65 | 1.6 |

## Audit Status

| audit status | rows |
| --- | --- |
| curated_pending_human_signoff | 1400 |
| built_in | 252 |

## External Baselines

External rows: `354`. Skipped rows: `354`.

| category | count |
| --- | --- |
| microsoft-graphrag external baseline skipped: set TORTUS_GRAPHRAG_COMMAND to a command template containing {query}. | 118 |
| llamaindex external baseline skipped: set TORTUS_LLAMA_INDEX_COMMAND to a command template containing {query}. | 118 |
| lightrag external baseline skipped: set TORTUS_LIGHTRAG_COMMAND to a command template containing {query}. | 118 |

## Boundary-Crossing Slice

| strategy | pass | source | path | precision | faith | portals | fanout | cross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.91 | 0.0 | 4.3 | 0.0 |
| bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.29 | 0.85 | 3.0 | 6.3 | 9.0 |
| community_summary_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.89 | 0.0 | 4.3 | 0.0 |
| euclidean_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.28 | 0.0 | 1.3 | 0.0 |
| graph_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.71 | 0.0 | 3.7 | 4.0 |
| graphrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 | 0.0 | 0.0 |
| hybrid_dense_bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 | 0.0 | 4.0 | 0.0 |
| hybrid_graph_rerank_local | 0.00 | 0.00 | 1.00 | 0.48 | 0.91 | 14.3 | 8.7 | 26.0 |
| lightrag_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 | 0.0 | 0.0 |
| llamaindex_external | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.0 | 0.0 | 0.0 |
| random_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.30 | 0.0 | 4.3 | 0.0 |
| tortus_torus | 0.00 | 0.00 | 0.33 | 0.04 | 0.76 | 0.3 | 4.0 | 4.7 |
| torus_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.28 | 0.0 | 1.3 | 0.0 |
| vector_only_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.85 | 0.0 | 3.0 | 0.0 |

## Failure Taxonomy

| category | count |
| --- | --- |
| missing_expected_sources | 1642 |
| missing_expected_path | 1279 |
| missing_expected_terms | 773 |
| low_faithfulness | 431 |
| low_path_precision | 328 |
| high_shard_fanout | 185 |
| warning_only | 6 |
| budget_limited | 5 |

## Cost And Fanout Notes

Highest mean shard fanout: `hybrid_graph_rerank_local` (8.9). Highest p95 latency: `hybrid_graph_rerank_local` (10.7 ms). Highest warning rate: `graphrag_external` (1.00). The V2 selectivity target is path recall >= 0.90, path precision >= 0.60, mean fanout <= 5.5, and mean portal hops <= 5.0.

## Hardest Misses

| question | strategy | term | source | path | precision | faith | warnings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| golden100-006-legacy-secret-cleanup | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.87 |  |
| golden100-012-audience-dashboard | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.91 |  |
| golden100-015-sidecar-distractor | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 |  |
| golden100-020-gateway-boundary | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.94 |  |
| golden100-035-sidecar-distractor | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.93 |  |
| golden100-052-audience-dashboard | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.94 |  |
| golden100-062-audience-dashboard | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.92 |  |
| golden100-076-legacy-secret-cleanup | bm25_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.89 |  |

## Reproduction

```bash
tortus ingest --corpus public-engineering
tortus index --layout torus --corpus public-engineering
tortus golden-set --out data/golden_set.json --count 100
tortus eval --suite benchmark --strategies all_with_external \
  --json-out data/eval/benchmark.json \
  --duckdb-out data/eval/results.duckdb
tortus report --eval-json data/eval/benchmark.json --out data/reports/eval-report.md
```
