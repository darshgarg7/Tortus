# Tortus Evaluation Report

Suite: `benchmark`. Rows: `1180`. A pass requires term recall >= 0.50, source recall >= 0.50, path recall >= 0.50, and faithfulness >= 0.50 for answerable questions. Negative questions pass only when unsupported answers are withheld. Skipped external adapters are reported separately and are not counted as wins. This is a local v2 benchmark, not a production superiority claim.

## Strategy Summary

| strategy | rows | pass | 95% CI | term | source | path | precision | faith | p50 ms | p95 ms | nodes | portals | fanout | cross | warn | skipped |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25_local | 118 | 0.02 | 0.00-0.04 | 1.00 | 0.63 | 0.03 | 0.03 | 0.88 | 0.9 | 1.1 | 5.0 | 0.0 | 4.2 | 0.0 | 0.01 | 0.00 |
| bounded_agentic_local | 118 | 0.64 | 0.55-0.72 | 0.99 | 0.63 | 0.95 | 0.86 | 0.89 | 2.4 | 3.3 | 5.7 | 3.0 | 4.4 | 3.7 | 0.00 | 0.00 |
| community_summary_local | 118 | 0.02 | 0.00-0.04 | 0.97 | 0.49 | 0.03 | 0.03 | 0.88 | 0.9 | 1.1 | 4.9 | 0.0 | 4.1 | 0.0 | 0.01 | 0.00 |
| euclidean_layout_local | 118 | 0.01 | 0.00-0.03 | 0.87 | 0.45 | 0.03 | 0.03 | 0.89 | 0.7 | 0.9 | 5.0 | 0.0 | 3.1 | 0.0 | 0.00 | 0.00 |
| graph_local | 118 | 0.14 | 0.08-0.21 | 0.96 | 0.57 | 0.17 | 0.34 | 0.88 | 1.4 | 2.5 | 5.8 | 0.0 | 4.3 | 4.2 | 0.02 | 0.00 |
| hybrid_dense_bm25_local | 118 | 0.01 | 0.00-0.03 | 0.97 | 0.69 | 0.03 | 0.03 | 0.88 | 1.4 | 2.1 | 5.0 | 0.0 | 4.4 | 0.0 | 0.00 | 0.00 |
| random_layout_local | 118 | 0.00 | 0.00-0.00 | 0.79 | 0.22 | 0.03 | 0.03 | 0.89 | 0.7 | 0.9 | 5.0 | 0.0 | 4.3 | 0.0 | 0.00 | 0.00 |
| tortus_torus | 118 | 0.77 | 0.70-0.85 | 1.00 | 0.72 | 1.00 | 0.64 | 0.88 | 2.3 | 4.9 | 7.0 | 3.5 | 5.2 | 5.6 | 0.02 | 0.00 |
| torus_layout_local | 118 | 0.01 | 0.00-0.03 | 0.88 | 0.51 | 0.03 | 0.03 | 0.88 | 0.8 | 1.0 | 5.0 | 0.0 | 3.1 | 0.0 | 0.00 | 0.00 |
| vector_only_local | 118 | 0.01 | 0.00-0.03 | 0.96 | 0.68 | 0.03 | 0.03 | 0.88 | 0.7 | 0.9 | 5.0 | 0.0 | 4.3 | 0.0 | 0.00 | 0.00 |

## Thesis Check

v2 supports keeping the toroidal traversal hypothesis alive: `tortus_torus` is +0.14 pass-rate points, +0.09 source-recall points, and +0.05 path-recall points, and -0.01 faithfulness points versus the strongest current baseline (`bounded_agentic_local`).

## Suite Breakdown

| suite | strategy | pass | source | path | precision | faith | p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| boundary_crossing | bm25_local | 0.00 | 0.61 | 0.00 | 0.00 | 0.89 | 0.9 |
| boundary_crossing | bounded_agentic_local | 1.00 | 0.72 | 1.00 | 0.87 | 0.89 | 2.7 |
| boundary_crossing | community_summary_local | 0.00 | 0.61 | 0.00 | 0.00 | 0.88 | 0.9 |
| boundary_crossing | euclidean_layout_local | 0.00 | 0.39 | 0.00 | 0.00 | 0.88 | 0.7 |
| boundary_crossing | graph_local | 0.00 | 0.50 | 0.00 | 0.21 | 0.88 | 1.6 |
| boundary_crossing | hybrid_dense_bm25_local | 0.00 | 0.83 | 0.00 | 0.00 | 0.88 | 1.4 |
| boundary_crossing | random_layout_local | 0.00 | 0.11 | 0.00 | 0.00 | 0.89 | 0.7 |
| boundary_crossing | tortus_torus | 1.00 | 0.72 | 1.00 | 0.71 | 0.88 | 2.5 |
| boundary_crossing | torus_layout_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.87 | 0.7 |
| boundary_crossing | vector_only_local | 0.00 | 0.50 | 0.00 | 0.00 | 0.88 | 0.6 |
| golden_candidate | bm25_local | 0.00 | 0.62 | 0.00 | 0.00 | 0.88 | 1.1 |
| golden_candidate | bounded_agentic_local | 0.63 | 0.63 | 0.95 | 0.88 | 0.89 | 3.4 |
| golden_candidate | community_summary_local | 0.00 | 0.48 | 0.00 | 0.00 | 0.88 | 1.3 |
| golden_candidate | euclidean_layout_local | 0.00 | 0.45 | 0.00 | 0.00 | 0.89 | 0.9 |
| golden_candidate | graph_local | 0.12 | 0.55 | 0.15 | 0.34 | 0.88 | 2.6 |
| golden_candidate | hybrid_dense_bm25_local | 0.00 | 0.69 | 0.00 | 0.00 | 0.88 | 2.2 |
| golden_candidate | random_layout_local | 0.00 | 0.22 | 0.00 | 0.00 | 0.89 | 0.9 |
| golden_candidate | tortus_torus | 0.76 | 0.70 | 1.00 | 0.65 | 0.88 | 4.9 |
| golden_candidate | torus_layout_local | 0.00 | 0.51 | 0.00 | 0.00 | 0.88 | 1.1 |
| golden_candidate | vector_only_local | 0.00 | 0.70 | 0.00 | 0.00 | 0.88 | 0.9 |
| multi_hop | bm25_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.88 | 0.9 |
| multi_hop | bounded_agentic_local | 0.33 | 0.56 | 0.83 | 0.87 | 0.89 | 2.7 |
| multi_hop | community_summary_local | 0.00 | 0.33 | 0.00 | 0.00 | 0.88 | 0.9 |
| multi_hop | euclidean_layout_local | 0.00 | 0.56 | 0.00 | 0.00 | 0.89 | 0.7 |
| multi_hop | graph_local | 0.00 | 0.56 | 0.17 | 0.42 | 0.86 | 1.8 |
| multi_hop | hybrid_dense_bm25_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.88 | 1.5 |
| multi_hop | random_layout_local | 0.00 | 0.33 | 0.00 | 0.00 | 0.89 | 0.7 |
| multi_hop | tortus_torus | 0.67 | 0.67 | 1.00 | 0.81 | 0.88 | 2.1 |
| multi_hop | torus_layout_local | 0.00 | 0.56 | 0.00 | 0.00 | 0.89 | 0.7 |
| multi_hop | vector_only_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.88 | 0.6 |
| negative | bm25_local | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 | 0.6 |
| negative | bounded_agentic_local | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 2.4 |
| negative | community_summary_local | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 | 0.6 |
| negative | euclidean_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.4 |
| negative | graph_local | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 1.5 |
| negative | hybrid_dense_bm25_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 1.0 |
| negative | random_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.4 |
| negative | tortus_torus | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 2.7 |
| negative | torus_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.5 |
| negative | vector_only_local | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.3 |
| single_hop | bm25_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.83 | 1.0 |
| single_hop | bounded_agentic_local | 1.00 | 1.00 | 1.00 | 0.25 | 0.85 | 1.9 |
| single_hop | community_summary_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.86 | 0.9 |
| single_hop | euclidean_layout_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.85 | 1.0 |
| single_hop | graph_local | 1.00 | 1.00 | 1.00 | 0.12 | 0.85 | 1.4 |
| single_hop | hybrid_dense_bm25_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.87 | 1.4 |
| single_hop | random_layout_local | 0.00 | 0.00 | 1.00 | 1.00 | 0.88 | 0.7 |
| single_hop | tortus_torus | 1.00 | 1.00 | 1.00 | 0.17 | 0.85 | 5.6 |
| single_hop | torus_layout_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.85 | 0.9 |
| single_hop | vector_only_local | 1.00 | 1.00 | 1.00 | 1.00 | 0.87 | 0.7 |
| stress | bm25_local | 0.00 | 0.74 | 0.00 | 0.00 | 0.88 | 0.8 |
| stress | bounded_agentic_local | 0.78 | 0.70 | 0.94 | 0.93 | 0.88 | 2.5 |
| stress | community_summary_local | 0.00 | 0.48 | 0.00 | 0.00 | 0.88 | 0.8 |
| stress | euclidean_layout_local | 0.00 | 0.52 | 0.00 | 0.00 | 0.88 | 0.7 |
| stress | graph_local | 0.22 | 0.63 | 0.17 | 0.38 | 0.87 | 1.3 |
| stress | hybrid_dense_bm25_local | 0.00 | 0.78 | 0.00 | 0.00 | 0.88 | 1.2 |
| stress | random_layout_local | 0.00 | 0.28 | 0.00 | 0.00 | 0.88 | 0.6 |
| stress | tortus_torus | 0.78 | 0.78 | 1.00 | 0.69 | 0.88 | 2.0 |
| stress | torus_layout_local | 0.00 | 0.56 | 0.00 | 0.00 | 0.88 | 0.7 |
| stress | vector_only_local | 0.00 | 0.70 | 0.00 | 0.00 | 0.88 | 0.7 |

## Audit Status

| audit status | rows |
| --- | --- |
| curated_pending_human_signoff | 1000 |
| built_in | 180 |

## External Baselines

No external baseline rows were requested.

## Boundary-Crossing Slice

| strategy | pass | source | path | precision | faith | portals | fanout | cross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25_local | 0.00 | 0.61 | 0.00 | 0.00 | 0.89 | 0.0 | 4.0 | 0.0 |
| bounded_agentic_local | 1.00 | 0.72 | 1.00 | 0.87 | 0.89 | 3.0 | 5.0 | 3.3 |
| community_summary_local | 0.00 | 0.61 | 0.00 | 0.00 | 0.88 | 0.0 | 3.7 | 0.0 |
| euclidean_layout_local | 0.00 | 0.39 | 0.00 | 0.00 | 0.88 | 0.0 | 2.7 | 0.0 |
| graph_local | 0.00 | 0.50 | 0.00 | 0.21 | 0.88 | 0.0 | 4.0 | 3.7 |
| hybrid_dense_bm25_local | 0.00 | 0.83 | 0.00 | 0.00 | 0.88 | 0.0 | 3.7 | 0.0 |
| random_layout_local | 0.00 | 0.11 | 0.00 | 0.00 | 0.89 | 0.0 | 4.7 | 0.0 |
| tortus_torus | 1.00 | 0.72 | 1.00 | 0.71 | 0.88 | 4.7 | 5.7 | 6.0 |
| torus_layout_local | 0.00 | 0.67 | 0.00 | 0.00 | 0.87 | 0.0 | 3.3 | 0.0 |
| vector_only_local | 0.00 | 0.50 | 0.00 | 0.00 | 0.88 | 0.0 | 3.3 | 0.0 |

## Failure Taxonomy

| category | count |
| --- | --- |
| missing_expected_path | 897 |
| missing_expected_sources | 120 |
| low_path_precision | 88 |
| high_shard_fanout | 22 |
| missing_expected_terms | 2 |
| candidate_generation_miss | 1 |
| warning_only | 1 |

## Cost And Fanout Notes

Highest mean shard fanout: `tortus_torus` (5.2). Highest p95 latency: `tortus_torus` (4.9 ms). Highest warning rate: `graph_local` (0.02). The V2 selectivity target is path recall >= 0.90, path precision >= 0.60, mean fanout <= 5.5, and mean portal hops <= 5.0.

## Hardest Misses

| question | strategy | term | source | path | precision | faith | warnings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| golden100-036-legacy-secret-cleanup | random_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.90 |  |
| golden100-046-legacy-secret-cleanup | random_layout_local | 0.00 | 0.00 | 0.00 | 0.00 | 0.90 |  |
| golden100-016-legacy-secret-cleanup | random_layout_local | 0.25 | 0.00 | 0.00 | 0.00 | 0.90 |  |
| golden100-026-legacy-secret-cleanup | random_layout_local | 0.25 | 0.00 | 0.00 | 0.00 | 0.89 |  |
| golden100-038-runbook-correlation | random_layout_local | 0.25 | 0.00 | 0.00 | 0.00 | 0.89 |  |
| golden100-076-legacy-secret-cleanup | random_layout_local | 0.25 | 0.00 | 0.00 | 0.00 | 0.85 |  |
| golden100-086-legacy-secret-cleanup | random_layout_local | 0.25 | 0.00 | 0.00 | 0.00 | 0.90 |  |
| golden100-035-sidecar-distractor | community_summary_local | 0.50 | 0.00 | 0.00 | 0.00 | 0.89 |  |

## Reproduction

```bash
tortus ingest --corpus public-engineering
tortus index --layout torus --corpus public-engineering
tortus golden-set --out data/golden_set.json --count 100
tortus eval --suite benchmark --strategies all \
  --json-out data/eval/benchmark.json \
  --duckdb-out data/eval/results.duckdb
tortus report --eval-json data/eval/benchmark.json --out data/reports/eval-report.md
```
