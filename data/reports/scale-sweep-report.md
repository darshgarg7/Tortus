# Tortus Scale Sweep Report

This report is a reproducible scale stress test over fetched public engineering-source text. The corpus is built by splitting real public pages from the Tortus manifest into source-preserving doclets. It is stronger than the toy demo, but it is still not a universal production superiority claim.

## Method

- Generated at: `2026-06-08T04:09:43.307582+00:00`
- Raw public sources in manifest: `10`
- Raw public sources fetched this run: `0` (cached snapshots are reused when this is `0`)
- Raw materialized documents: `10`
- Raw chunks at normal chunking: `526`
- Doclet size: `150` characters
- Max shared-phrase edges per phrase: `96`
- Sweep sizes: `50, 200, 500, 1000` documents
- Strategies: `tortus_torus, vector_only_local, bm25_local, hybrid_dense_bm25_local, hybrid_graph_rerank_local`
- Python/platform: `3.12.7` on `macOS-14.8.3-arm64-arm-64bit`
- Total elapsed: `369.3` seconds

## Summary By Corpus Size

| docs | strategy | pass | source | path | faith | p95 ms | fanout | portals | build s | eval s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 | bm25_local | 0.00 | 0.67 | 0.00 | 0.81 | 3.8 | 3.2 | 0.0 | 11.7 | 0.6 |
| 50 | hybrid_dense_bm25_local | 0.00 | 0.83 | 0.00 | 0.82 | 3.1 | 4.2 | 0.0 | 11.7 | 0.6 |
| 50 | hybrid_graph_rerank_local | 0.50 | 0.83 | 1.00 | 0.82 | 3.8 | 10.7 | 11.8 | 11.7 | 0.6 |
| 50 | tortus_torus | 0.50 | 0.58 | 0.67 | 0.63 | 172.0 | 5.7 | 0.3 | 11.7 | 0.6 |
| 50 | vector_only_local | 0.00 | 0.75 | 0.00 | 0.67 | 2.9 | 4.0 | 0.0 | 11.7 | 0.6 |
| 200 | bm25_local | 0.00 | 0.67 | 0.00 | 0.83 | 7.6 | 3.2 | 0.0 | 41.6 | 0.8 |
| 200 | hybrid_dense_bm25_local | 0.00 | 0.67 | 0.00 | 0.84 | 47.4 | 3.3 | 0.0 | 41.6 | 0.8 |
| 200 | hybrid_graph_rerank_local | 0.83 | 0.83 | 1.00 | 0.81 | 13.1 | 7.3 | 8.7 | 41.6 | 0.8 |
| 200 | tortus_torus | 0.67 | 0.67 | 0.67 | 0.68 | 164.2 | 3.3 | 0.8 | 41.6 | 0.8 |
| 200 | vector_only_local | 0.00 | 0.75 | 0.00 | 0.69 | 3.6 | 3.0 | 0.0 | 41.6 | 0.8 |
| 500 | bm25_local | 0.00 | 0.75 | 0.00 | 0.84 | 64.2 | 3.2 | 0.0 | 104.2 | 1.5 |
| 500 | hybrid_dense_bm25_local | 0.00 | 0.75 | 0.00 | 0.84 | 33.8 | 3.3 | 0.0 | 104.2 | 1.5 |
| 500 | hybrid_graph_rerank_local | 0.67 | 0.75 | 0.75 | 0.83 | 24.9 | 8.0 | 5.2 | 104.2 | 1.5 |
| 500 | tortus_torus | 0.67 | 0.67 | 0.67 | 0.82 | 210.3 | 3.3 | 0.5 | 104.2 | 1.5 |
| 500 | vector_only_local | 0.00 | 0.75 | 0.00 | 0.80 | 55.8 | 2.8 | 0.0 | 104.2 | 1.5 |
| 1000 | bm25_local | 0.00 | 0.67 | 0.00 | 0.83 | 98.9 | 3.3 | 0.0 | 205.2 | 2.1 |
| 1000 | hybrid_dense_bm25_local | 0.00 | 0.75 | 0.00 | 0.82 | 117.8 | 3.5 | 0.0 | 205.2 | 2.1 |
| 1000 | hybrid_graph_rerank_local | 1.00 | 0.75 | 1.00 | 0.83 | 92.5 | 8.2 | 5.5 | 205.2 | 2.1 |
| 1000 | tortus_torus | 0.83 | 0.75 | 0.83 | 0.76 | 162.2 | 4.0 | 0.7 | 205.2 | 2.1 |
| 1000 | vector_only_local | 0.00 | 0.83 | 0.00 | 0.81 | 19.0 | 3.0 | 0.0 | 205.2 | 2.1 |

## Strategy Trend

### `bm25_local`

- Pass rate by docs: 50:0.00, 200:0.00, 500:0.00, 1000:0.00
- Path recall by docs: 50:0.00, 200:0.00, 500:0.00, 1000:0.00
- P95 latency by docs: 50:3.8ms, 200:7.6ms, 500:64.2ms, 1000:98.9ms

### `hybrid_dense_bm25_local`

- Pass rate by docs: 50:0.00, 200:0.00, 500:0.00, 1000:0.00
- Path recall by docs: 50:0.00, 200:0.00, 500:0.00, 1000:0.00
- P95 latency by docs: 50:3.1ms, 200:47.4ms, 500:33.8ms, 1000:117.8ms

### `hybrid_graph_rerank_local`

- Pass rate by docs: 50:0.50, 200:0.83, 500:0.67, 1000:1.00
- Path recall by docs: 50:1.00, 200:1.00, 500:0.75, 1000:1.00
- P95 latency by docs: 50:3.8ms, 200:13.1ms, 500:24.9ms, 1000:92.5ms

### `tortus_torus`

- Pass rate by docs: 50:0.50, 200:0.67, 500:0.67, 1000:0.83
- Path recall by docs: 50:0.67, 200:0.67, 500:0.67, 1000:0.83
- P95 latency by docs: 50:172.0ms, 200:164.2ms, 500:210.3ms, 1000:162.2ms

### `vector_only_local`

- Pass rate by docs: 50:0.00, 200:0.00, 500:0.00, 1000:0.00
- Path recall by docs: 50:0.00, 200:0.00, 500:0.00, 1000:0.00
- P95 latency by docs: 50:2.9ms, 200:3.6ms, 500:55.8ms, 1000:19.0ms

## Caveats

- The sweep uses public-source doclets, not a private enterprise corpus.
- Labels are source/term/path heuristics tailored to the fetched public manifest.
- Local hash embeddings are deterministic and reproducible, but not a substitute for reporting API embedding variability.
- This run tests scale mechanics, latency, and relative retrieval behavior; larger audited corpora are still needed for a publication-grade claim.
