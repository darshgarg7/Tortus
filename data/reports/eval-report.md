# Tortus Evaluation Report

Suite: `benchmark`. Rows: `1160`. A pass requires term recall >= 0.50, source recall >= 0.50, and path recall >= 0.50. This is a local v0 benchmark, not a production superiority claim.

## Strategy Summary

| strategy | pass | term | source | path | p50 ms | p95 ms | nodes | portals | fanout | cross | warn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm25 | 0.01 | 0.99 | 0.73 | 0.01 | 0.3 | 0.4 | 5.0 | 0.0 | 4.4 | 0.0 | 0.00 |
| bounded_agentic | 0.84 | 0.98 | 0.73 | 1.00 | 1.3 | 1.8 | 5.0 | 3.0 | 4.5 | 3.7 | 0.00 |
| community_summary | 0.01 | 0.96 | 0.61 | 0.01 | 0.3 | 0.4 | 4.5 | 0.0 | 3.9 | 0.0 | 0.00 |
| euclidean_layout | 0.01 | 0.86 | 0.62 | 0.01 | 0.3 | 0.4 | 5.0 | 0.0 | 4.7 | 0.0 | 0.00 |
| graph_local | 0.21 | 0.98 | 0.98 | 0.16 | 0.9 | 1.2 | 10.2 | 0.0 | 8.0 | 4.9 | 0.00 |
| hybrid_dense_bm25 | 0.01 | 0.98 | 0.82 | 0.01 | 0.6 | 0.8 | 5.0 | 0.0 | 4.5 | 0.0 | 0.00 |
| random_layout | 0.01 | 0.85 | 0.46 | 0.01 | 0.2 | 0.4 | 5.0 | 0.0 | 4.6 | 0.0 | 0.00 |
| tortus_torus | 0.94 | 0.95 | 0.89 | 1.00 | 1.1 | 1.6 | 11.2 | 8.0 | 8.6 | 12.3 | 1.00 |
| torus_layout | 0.01 | 0.86 | 0.64 | 0.01 | 0.4 | 0.6 | 5.0 | 0.0 | 4.2 | 0.0 | 0.00 |
| vector_only | 0.01 | 0.95 | 0.79 | 0.01 | 0.3 | 0.6 | 5.0 | 0.0 | 4.6 | 0.0 | 0.00 |

## Thesis Check

v0 supports keeping the toroidal traversal hypothesis alive: `tortus_torus` is +0.10 pass-rate points, +0.17 source-recall points, and +0.00 path-recall points versus the strongest current baseline (`bounded_agentic`).

## Suite Breakdown

| suite | strategy | pass | source | path | p95 ms |
| --- | --- | --- | --- | --- | --- |
| boundary_crossing | bm25 | 0.00 | 0.72 | 0.00 | 0.3 |
| boundary_crossing | bounded_agentic | 1.00 | 0.72 | 1.00 | 1.9 |
| boundary_crossing | community_summary | 0.00 | 0.61 | 0.00 | 0.5 |
| boundary_crossing | euclidean_layout | 0.00 | 0.50 | 0.00 | 0.4 |
| boundary_crossing | graph_local | 0.00 | 1.00 | 0.00 | 1.5 |
| boundary_crossing | hybrid_dense_bm25 | 0.00 | 0.83 | 0.00 | 0.7 |
| boundary_crossing | random_layout | 0.00 | 0.61 | 0.00 | 0.3 |
| boundary_crossing | tortus_torus | 1.00 | 0.89 | 1.00 | 2.3 |
| boundary_crossing | torus_layout | 0.00 | 0.78 | 0.00 | 0.5 |
| boundary_crossing | vector_only | 0.00 | 0.72 | 0.00 | 0.6 |
| golden_candidate | bm25 | 0.00 | 0.71 | 0.00 | 0.3 |
| golden_candidate | bounded_agentic | 0.83 | 0.73 | 1.00 | 1.6 |
| golden_candidate | community_summary | 0.00 | 0.61 | 0.00 | 0.4 |
| golden_candidate | euclidean_layout | 0.00 | 0.63 | 0.00 | 0.4 |
| golden_candidate | graph_local | 0.20 | 0.98 | 0.15 | 1.1 |
| golden_candidate | hybrid_dense_bm25 | 0.00 | 0.82 | 0.00 | 0.7 |
| golden_candidate | random_layout | 0.00 | 0.45 | 0.00 | 0.3 |
| golden_candidate | tortus_torus | 0.93 | 0.88 | 1.00 | 1.3 |
| golden_candidate | torus_layout | 0.00 | 0.65 | 0.00 | 0.6 |
| golden_candidate | vector_only | 0.00 | 0.79 | 0.00 | 0.5 |
| multi_hop | bm25 | 0.00 | 0.67 | 0.00 | 0.5 |
| multi_hop | bounded_agentic | 0.67 | 0.67 | 1.00 | 2.0 |
| multi_hop | community_summary | 0.00 | 0.56 | 0.00 | 0.3 |
| multi_hop | euclidean_layout | 0.00 | 0.56 | 0.00 | 0.4 |
| multi_hop | graph_local | 0.33 | 0.89 | 0.17 | 1.0 |
| multi_hop | hybrid_dense_bm25 | 0.00 | 0.67 | 0.00 | 0.8 |
| multi_hop | random_layout | 0.00 | 0.56 | 0.00 | 0.3 |
| multi_hop | tortus_torus | 1.00 | 1.00 | 1.00 | 1.8 |
| multi_hop | torus_layout | 0.00 | 0.56 | 0.00 | 0.5 |
| multi_hop | vector_only | 0.00 | 0.78 | 0.00 | 0.7 |
| single_hop | bm25 | 1.00 | 1.00 | 1.00 | 0.5 |
| single_hop | bounded_agentic | 1.00 | 1.00 | 1.00 | 1.5 |
| single_hop | community_summary | 1.00 | 1.00 | 1.00 | 0.4 |
| single_hop | euclidean_layout | 1.00 | 1.00 | 1.00 | 0.3 |
| single_hop | graph_local | 1.00 | 1.00 | 1.00 | 1.4 |
| single_hop | hybrid_dense_bm25 | 1.00 | 1.00 | 1.00 | 1.0 |
| single_hop | random_layout | 1.00 | 1.00 | 1.00 | 0.3 |
| single_hop | tortus_torus | 1.00 | 1.00 | 1.00 | 2.3 |
| single_hop | torus_layout | 1.00 | 1.00 | 1.00 | 0.5 |
| single_hop | vector_only | 1.00 | 1.00 | 1.00 | 0.4 |
| stress | bm25 | 0.00 | 0.85 | 0.00 | 0.4 |
| stress | bounded_agentic | 0.89 | 0.74 | 1.00 | 1.4 |
| stress | community_summary | 0.00 | 0.63 | 0.00 | 0.4 |
| stress | euclidean_layout | 0.00 | 0.57 | 0.00 | 0.3 |
| stress | graph_local | 0.22 | 1.00 | 0.17 | 1.0 |
| stress | hybrid_dense_bm25 | 0.00 | 0.81 | 0.00 | 0.9 |
| stress | random_layout | 0.00 | 0.44 | 0.00 | 0.4 |
| stress | tortus_torus | 1.00 | 0.96 | 1.00 | 2.2 |
| stress | torus_layout | 0.00 | 0.50 | 0.00 | 0.6 |
| stress | vector_only | 0.00 | 0.78 | 0.00 | 0.6 |

## Boundary-Crossing Slice

| strategy | pass | source | path | portals | fanout | cross |
| --- | --- | --- | --- | --- | --- | --- |
| bm25 | 0.00 | 0.72 | 0.00 | 0.0 | 4.3 | 0.0 |
| bounded_agentic | 1.00 | 0.72 | 1.00 | 3.0 | 4.3 | 3.0 |
| community_summary | 0.00 | 0.61 | 0.00 | 0.0 | 3.3 | 0.0 |
| euclidean_layout | 0.00 | 0.50 | 0.00 | 0.0 | 4.7 | 0.0 |
| graph_local | 0.00 | 1.00 | 0.00 | 0.0 | 8.3 | 5.0 |
| hybrid_dense_bm25 | 0.00 | 0.83 | 0.00 | 0.0 | 5.0 | 0.0 |
| random_layout | 0.00 | 0.61 | 0.00 | 0.0 | 4.3 | 0.0 |
| tortus_torus | 1.00 | 0.89 | 1.00 | 8.0 | 8.7 | 13.0 |
| torus_layout | 0.00 | 0.78 | 0.00 | 0.0 | 4.0 | 0.0 |
| vector_only | 0.00 | 0.72 | 0.00 | 0.0 | 5.0 | 0.0 |

## Failure Taxonomy

| category | count |
| --- | --- |
| missing_expected_path | 897 |
| high_shard_fanout | 208 |
| budget_limited | 116 |
| missing_expected_sources | 20 |

## Cost And Fanout Notes

Highest mean shard fanout: `tortus_torus` (8.6). Highest p95 latency: `bounded_agentic` (1.8 ms). Highest warning rate: `tortus_torus` (1.00).

## Hardest Misses

| question | strategy | term | source | path | warnings |
| --- | --- | --- | --- | --- | --- |
| golden100-036-legacy-secret-cleanup | random_layout | 0.50 | 0.00 | 0.00 |  |
| golden100-068-runbook-correlation | random_layout | 0.50 | 0.00 | 0.00 |  |
| golden100-075-sidecar-distractor | random_layout | 0.50 | 0.00 | 0.00 |  |
| golden100-088-runbook-correlation | random_layout | 0.50 | 0.00 | 0.00 |  |
| golden100-015-sidecar-distractor | torus_layout | 0.50 | 0.00 | 0.00 |  |
| golden100-069-policy-to-observability | community_summary | 0.75 | 0.00 | 0.00 |  |
| golden100-079-policy-to-observability | community_summary | 0.75 | 0.00 | 0.00 |  |
| golden100-099-policy-to-observability | community_summary | 0.75 | 0.00 | 0.00 |  |

## Reproduction

```bash
tortus ingest --corpus engineering
tortus index --layout torus
tortus golden-set --out data/golden_set.json --count 100
tortus eval --suite benchmark --strategies all \
  --json-out data/eval/benchmark.json \
  --duckdb-out data/eval/results.duckdb
tortus report --eval-json data/eval/benchmark.json --out data/reports/eval-report.md
```
