# Tortus Evaluation Report

Suite: `benchmark`. Rows: `1180`. A pass requires term recall >= 0.50, source recall >= 0.50, path recall >= 0.50, and faithfulness >= 0.50 for answerable questions. Negative questions pass only when unsupported answers are withheld. This is a local v1 benchmark, not a production superiority claim.

## Strategy Summary

| strategy | pass | term | source | path | precision | faith | p50 ms | p95 ms | nodes | portals | fanout | cross | warn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25 | 0.02 | 1.00 | 0.63 | 0.03 | 0.03 | 0.88 | 0.7 | 1.1 | 5.0 | 0.0 | 4.2 | 0.0 | 0.01 |
| bounded_agentic | 0.64 | 0.99 | 0.63 | 0.95 | 0.86 | 0.89 | 2.5 | 4.0 | 5.7 | 3.0 | 4.4 | 3.7 | 0.00 |
| community_summary | 0.02 | 0.97 | 0.49 | 0.03 | 0.03 | 0.88 | 0.7 | 1.4 | 4.9 | 0.0 | 4.1 | 0.0 | 0.01 |
| euclidean_layout | 0.01 | 0.87 | 0.45 | 0.03 | 0.03 | 0.89 | 0.6 | 1.1 | 5.0 | 0.0 | 3.1 | 0.0 | 0.00 |
| graph_local | 0.16 | 0.97 | 0.73 | 0.17 | 0.17 | 0.86 | 2.5 | 4.2 | 16.3 | 0.0 | 9.1 | 15.7 | 0.02 |
| hybrid_dense_bm25 | 0.01 | 0.97 | 0.69 | 0.03 | 0.03 | 0.88 | 1.3 | 2.3 | 5.0 | 0.0 | 4.4 | 0.0 | 0.00 |
| random_layout | 0.00 | 0.79 | 0.22 | 0.03 | 0.03 | 0.89 | 0.6 | 1.1 | 5.0 | 0.0 | 4.3 | 0.0 | 0.00 |
| tortus_torus | 0.73 | 0.99 | 0.70 | 1.00 | 0.44 | 0.86 | 3.4 | 5.7 | 18.1 | 7.9 | 9.6 | 19.5 | 0.02 |
| torus_layout | 0.01 | 0.88 | 0.51 | 0.03 | 0.03 | 0.88 | 0.7 | 1.3 | 5.0 | 0.0 | 3.1 | 0.0 | 0.00 |
| vector_only | 0.01 | 0.96 | 0.68 | 0.03 | 0.03 | 0.88 | 0.6 | 0.9 | 5.0 | 0.0 | 4.3 | 0.0 | 0.00 |

## Thesis Check

v1 supports keeping the toroidal traversal hypothesis alive: `tortus_torus` is +0.09 pass-rate points, +0.07 source-recall points, and +0.05 path-recall points, and -0.03 faithfulness points versus the strongest current baseline (`bounded_agentic`).

## Suite Breakdown

| suite | strategy | pass | source | path | precision | faith | p95 ms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| boundary_crossing | bm25 | 0.00 | 0.61 | 0.00 | 0.00 | 0.89 | 1.0 |
| boundary_crossing | bounded_agentic | 1.00 | 0.72 | 1.00 | 0.87 | 0.89 | 2.7 |
| boundary_crossing | community_summary | 0.00 | 0.61 | 0.00 | 0.00 | 0.88 | 0.9 |
| boundary_crossing | euclidean_layout | 0.00 | 0.39 | 0.00 | 0.00 | 0.88 | 0.7 |
| boundary_crossing | graph_local | 0.00 | 0.89 | 0.00 | 0.05 | 0.87 | 3.3 |
| boundary_crossing | hybrid_dense_bm25 | 0.00 | 0.83 | 0.00 | 0.00 | 0.88 | 1.7 |
| boundary_crossing | random_layout | 0.00 | 0.11 | 0.00 | 0.00 | 0.89 | 0.8 |
| boundary_crossing | tortus_torus | 1.00 | 0.89 | 1.00 | 0.39 | 0.84 | 3.9 |
| boundary_crossing | torus_layout | 0.00 | 0.67 | 0.00 | 0.00 | 0.87 | 0.9 |
| boundary_crossing | vector_only | 0.00 | 0.50 | 0.00 | 0.00 | 0.88 | 0.9 |
| golden_candidate | bm25 | 0.00 | 0.62 | 0.00 | 0.00 | 0.88 | 1.1 |
| golden_candidate | bounded_agentic | 0.63 | 0.63 | 0.95 | 0.88 | 0.89 | 4.3 |
| golden_candidate | community_summary | 0.00 | 0.48 | 0.00 | 0.00 | 0.88 | 1.4 |
| golden_candidate | euclidean_layout | 0.00 | 0.45 | 0.00 | 0.00 | 0.89 | 1.1 |
| golden_candidate | graph_local | 0.14 | 0.72 | 0.15 | 0.18 | 0.85 | 5.2 |
| golden_candidate | hybrid_dense_bm25 | 0.00 | 0.69 | 0.00 | 0.00 | 0.88 | 1.9 |
| golden_candidate | random_layout | 0.00 | 0.22 | 0.00 | 0.00 | 0.89 | 1.1 |
| golden_candidate | tortus_torus | 0.72 | 0.69 | 1.00 | 0.44 | 0.86 | 5.7 |
| golden_candidate | torus_layout | 0.00 | 0.51 | 0.00 | 0.00 | 0.88 | 1.6 |
| golden_candidate | vector_only | 0.00 | 0.70 | 0.00 | 0.00 | 0.88 | 0.9 |
| multi_hop | bm25 | 0.00 | 0.67 | 0.00 | 0.00 | 0.88 | 1.0 |
| multi_hop | bounded_agentic | 0.33 | 0.56 | 0.83 | 0.87 | 0.89 | 3.4 |
| multi_hop | community_summary | 0.00 | 0.33 | 0.00 | 0.00 | 0.88 | 0.9 |
| multi_hop | euclidean_layout | 0.00 | 0.56 | 0.00 | 0.00 | 0.89 | 0.8 |
| multi_hop | graph_local | 0.00 | 0.56 | 0.17 | 0.24 | 0.85 | 3.3 |
| multi_hop | hybrid_dense_bm25 | 0.00 | 0.67 | 0.00 | 0.00 | 0.88 | 1.7 |
| multi_hop | random_layout | 0.00 | 0.33 | 0.00 | 0.00 | 0.89 | 0.8 |
| multi_hop | tortus_torus | 0.33 | 0.56 | 1.00 | 0.54 | 0.87 | 3.8 |
| multi_hop | torus_layout | 0.00 | 0.56 | 0.00 | 0.00 | 0.89 | 1.0 |
| multi_hop | vector_only | 0.00 | 0.67 | 0.00 | 0.00 | 0.88 | 0.8 |
| negative | bm25 | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 | 0.7 |
| negative | bounded_agentic | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 3.1 |
| negative | community_summary | 0.50 | 0.50 | 1.00 | 1.00 | 1.00 | 0.8 |
| negative | euclidean_layout | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.9 |
| negative | graph_local | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 3.5 |
| negative | hybrid_dense_bm25 | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 3.0 |
| negative | random_layout | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.8 |
| negative | tortus_torus | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 5.4 |
| negative | torus_layout | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.8 |
| negative | vector_only | 0.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.6 |
| single_hop | bm25 | 1.00 | 1.00 | 1.00 | 1.00 | 0.83 | 2.1 |
| single_hop | bounded_agentic | 1.00 | 1.00 | 1.00 | 0.25 | 0.85 | 2.2 |
| single_hop | community_summary | 1.00 | 1.00 | 1.00 | 1.00 | 0.86 | 0.9 |
| single_hop | euclidean_layout | 1.00 | 1.00 | 1.00 | 1.00 | 0.85 | 0.8 |
| single_hop | graph_local | 1.00 | 1.00 | 1.00 | 0.04 | 0.88 | 4.0 |
| single_hop | hybrid_dense_bm25 | 1.00 | 1.00 | 1.00 | 1.00 | 0.87 | 2.2 |
| single_hop | random_layout | 0.00 | 0.00 | 1.00 | 1.00 | 0.88 | 0.7 |
| single_hop | tortus_torus | 1.00 | 1.00 | 1.00 | 0.03 | 0.87 | 9.1 |
| single_hop | torus_layout | 1.00 | 1.00 | 1.00 | 1.00 | 0.85 | 0.8 |
| single_hop | vector_only | 1.00 | 1.00 | 1.00 | 1.00 | 0.87 | 0.7 |
| stress | bm25 | 0.00 | 0.74 | 0.00 | 0.00 | 0.88 | 1.0 |
| stress | bounded_agentic | 0.78 | 0.70 | 0.94 | 0.93 | 0.88 | 2.9 |
| stress | community_summary | 0.00 | 0.48 | 0.00 | 0.00 | 0.88 | 1.5 |
| stress | euclidean_layout | 0.00 | 0.52 | 0.00 | 0.00 | 0.88 | 0.7 |
| stress | graph_local | 0.22 | 0.78 | 0.17 | 0.18 | 0.85 | 3.7 |
| stress | hybrid_dense_bm25 | 0.00 | 0.78 | 0.00 | 0.00 | 0.88 | 1.6 |
| stress | random_layout | 0.00 | 0.28 | 0.00 | 0.00 | 0.88 | 1.1 |
| stress | tortus_torus | 0.78 | 0.70 | 1.00 | 0.47 | 0.87 | 3.8 |
| stress | torus_layout | 0.00 | 0.56 | 0.00 | 0.00 | 0.88 | 0.9 |
| stress | vector_only | 0.00 | 0.70 | 0.00 | 0.00 | 0.88 | 0.8 |

## Boundary-Crossing Slice

| strategy | pass | source | path | precision | faith | portals | fanout | cross |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25 | 0.00 | 0.61 | 0.00 | 0.00 | 0.89 | 0.0 | 4.0 | 0.0 |
| bounded_agentic | 1.00 | 0.72 | 1.00 | 0.87 | 0.89 | 3.0 | 5.0 | 3.3 |
| community_summary | 0.00 | 0.61 | 0.00 | 0.00 | 0.88 | 0.0 | 3.7 | 0.0 |
| euclidean_layout | 0.00 | 0.39 | 0.00 | 0.00 | 0.88 | 0.0 | 2.7 | 0.0 |
| graph_local | 0.00 | 0.89 | 0.00 | 0.05 | 0.87 | 0.0 | 9.7 | 16.7 |
| hybrid_dense_bm25 | 0.00 | 0.83 | 0.00 | 0.00 | 0.88 | 0.0 | 3.7 | 0.0 |
| random_layout | 0.00 | 0.11 | 0.00 | 0.00 | 0.89 | 0.0 | 4.7 | 0.0 |
| tortus_torus | 1.00 | 0.89 | 1.00 | 0.39 | 0.84 | 8.0 | 9.7 | 19.7 |
| torus_layout | 0.00 | 0.67 | 0.00 | 0.00 | 0.87 | 0.0 | 3.3 | 0.0 |
| vector_only | 0.00 | 0.50 | 0.00 | 0.00 | 0.88 | 0.0 | 3.3 | 0.0 |

## Failure Taxonomy

| category | count |
| --- | --- |
| missing_expected_path | 897 |
| high_shard_fanout | 134 |
| missing_expected_sources | 121 |
| low_path_precision | 120 |
| missing_expected_terms | 2 |
| candidate_generation_miss | 1 |
| warning_only | 1 |

## Cost And Fanout Notes

Highest mean shard fanout: `tortus_torus` (9.6). Highest p95 latency: `tortus_torus` (5.7 ms). Highest warning rate: `graph_local` (0.02).

## Hardest Misses

| question | strategy | term | source | path | precision | faith | warnings |
| --- | --- | --- | --- | --- | --- | --- | --- |
| golden100-036-legacy-secret-cleanup | random_layout | 0.00 | 0.00 | 0.00 | 0.00 | 0.90 |  |
| golden100-046-legacy-secret-cleanup | random_layout | 0.00 | 0.00 | 0.00 | 0.00 | 0.90 |  |
| golden100-016-legacy-secret-cleanup | random_layout | 0.25 | 0.00 | 0.00 | 0.00 | 0.90 |  |
| golden100-026-legacy-secret-cleanup | random_layout | 0.25 | 0.00 | 0.00 | 0.00 | 0.89 |  |
| golden100-038-runbook-correlation | random_layout | 0.25 | 0.00 | 0.00 | 0.00 | 0.89 |  |
| golden100-076-legacy-secret-cleanup | random_layout | 0.25 | 0.00 | 0.00 | 0.00 | 0.85 |  |
| golden100-086-legacy-secret-cleanup | random_layout | 0.25 | 0.00 | 0.00 | 0.00 | 0.90 |  |
| golden100-035-sidecar-distractor | community_summary | 0.50 | 0.00 | 0.00 | 0.00 | 0.89 |  |

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
