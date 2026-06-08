"""Run a reproducible public-corpus scale sweep for Tortus.

The sweep uses fetched public engineering sources, splits them into source-preserving
doclets, and evaluates retrieval at multiple corpus sizes. It is a scale stress test
over real public-source-derived text, not a broad production superiority claim.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from tortus.config import Settings, settings_with_overrides
from tortus.corpus import chunk_corpus, write_snapshot
from tortus.corpus_manifest import fetch_or_verify_public_corpus
from tortus.eval import EvalReport, run_eval
from tortus.models import Document
from tortus.pipeline import build_index, load_engine
from tortus.report import strategy_summaries


@dataclass(frozen=True)
class SweepCell:
    """One scale-sweep result cell."""

    doc_count: int
    chunks: int
    strategy: str
    rows: int
    pass_rate: float
    source_recall: float
    path_recall: float
    faithfulness: float
    p95_latency_ms: float
    mean_shard_fanout: float
    mean_portal_hops: float
    build_seconds: float
    eval_seconds: float


def main() -> int:
    """Run the scale sweep and write reports."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(".tortus/scale-sweep/data"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".tortus/scale-sweep/cache"))
    parser.add_argument("--raw-corpus", default="scale-public-raw")
    parser.add_argument("--doclet-chars", type=int, default=150)
    parser.add_argument("--sizes", default="50,200,500,1000")
    parser.add_argument(
        "--max-edges-per-phrase",
        type=int,
        default=96,
        help="Cap deterministic shared-phrase edges per phrase; use -1 for unbounded.",
    )
    parser.add_argument(
        "--strategies",
        default="tortus_torus,vector_only_local,bm25_local,hybrid_dense_bm25_local,hybrid_graph_rerank_local",
    )
    parser.add_argument("--json-out", type=Path, default=Path("data/eval/scale-sweep.json"))
    parser.add_argument(
        "--report-out",
        type=Path,
        default=Path("data/reports/scale-sweep-report.md"),
    )
    parser.add_argument(
        "--fetch",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fetch live public sources before building the sweep corpus.",
    )
    args = parser.parse_args()

    started_at = time.perf_counter()
    edge_cap = None if args.max_edges_per_phrase < 0 else args.max_edges_per_phrase
    settings = Settings(TORTUS_DATA_DIR=args.data_dir, TORTUS_CACHE_DIR=args.cache_dir)
    print("[scale] fetching/materializing public corpus", flush=True)
    fetch_result = fetch_or_verify_public_corpus(
        settings,
        fetch=args.fetch,
        materialize=True,
        corpus_name=args.raw_corpus,
    )
    raw_dir = settings.tortus_data_dir / "corpus" / args.raw_corpus
    raw_docs = load_documents(raw_dir)
    doclets = make_doclets(raw_docs, max_chars=args.doclet_chars)
    sizes = [int(value.strip()) for value in args.sizes.split(",") if value.strip()]
    strategies = tuple(value.strip() for value in args.strategies.split(",") if value.strip())
    if max(sizes) > len(doclets):
        raise ValueError(
            f"requested {max(sizes)} doclets but only {len(doclets)} are available; "
            "lower --doclet-chars or reduce --sizes"
        )
    print(
        "[scale] prepared "
        f"{len(doclets)} doclets from {len(raw_docs)} public documents; "
        f"sizes={sizes}; strategies={len(strategies)}; edge_cap={edge_cap}",
        flush=True,
    )

    cells: list[SweepCell] = []
    reports: dict[str, EvalReport] = {}
    for size in sizes:
        print(f"[scale] {size} docs: writing source-preserving corpus", flush=True)
        corpus_name = f"scale-public-{size}"
        corpus_dir = settings.tortus_data_dir / "corpus" / corpus_name
        documents = doclets[:size]
        chunks = chunk_corpus(documents)
        write_snapshot(documents, chunks, corpus_dir)
        (corpus_dir / "snapshot_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "generated_at": datetime.now(tz=UTC).isoformat(),
                    "corpus": corpus_name,
                    "method": "round_robin_doclets_from_fetched_public_sources",
                    "raw_corpus": args.raw_corpus,
                    "doclet_chars": args.doclet_chars,
                    "max_edges_per_phrase": edge_cap,
                    "documents": len(documents),
                    "chunks": len(chunks),
                    "source_manifest": str(fetch_result.out_path),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        run_settings = settings_with_overrides(settings, corpus=corpus_name)
        build_started_at = time.perf_counter()
        print(f"[scale] {size} docs: building index", flush=True)
        build_index(run_settings, corpus=corpus_name, max_edges_per_phrase=edge_cap)
        build_seconds = time.perf_counter() - build_started_at
        engine = load_engine(run_settings)
        try:
            eval_started_at = time.perf_counter()
            print(f"[scale] {size} docs: running eval strategies", flush=True)
            report = run_eval(engine, suite="scale_sweep", strategies=strategies)
            eval_seconds = time.perf_counter() - eval_started_at
        finally:
            engine.graph.close()
        reports[str(size)] = report
        for summary in strategy_summaries(report):
            cells.append(
                SweepCell(
                    doc_count=size,
                    chunks=len(chunks),
                    strategy=summary.strategy,
                    rows=summary.rows,
                    pass_rate=summary.pass_rate,
                    source_recall=summary.source_recall,
                    path_recall=summary.path_recall,
                    faithfulness=summary.faithfulness,
                    p95_latency_ms=summary.p95_latency_ms,
                    mean_shard_fanout=summary.mean_shard_fanout,
                    mean_portal_hops=summary.mean_portal_hops,
                    build_seconds=build_seconds,
                    eval_seconds=eval_seconds,
                )
            )
        print(
            f"[scale] {size} docs: done in build={build_seconds:.1f}s "
            f"eval={eval_seconds:.1f}s",
            flush=True,
        )

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "elapsed_seconds": time.perf_counter() - started_at,
        "method": "public_source_doclet_scale_sweep",
        "doclet_chars": args.doclet_chars,
        "max_edges_per_phrase": edge_cap,
        "sizes": sizes,
        "strategies": list(strategies),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "raw_sources": fetch_result.sources,
        "raw_fetched": fetch_result.fetched,
        "raw_documents": fetch_result.documents,
        "raw_chunks": fetch_result.chunks,
        "cells": [asdict(cell) for cell in cells],
        "reports": {
            size: report.model_dump(mode="json") for size, report in reports.items()
        },
        "warnings": fetch_result.warnings,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(render_markdown(payload, cells), encoding="utf-8")
    print(f"wrote {args.json_out}")
    print(f"wrote {args.report_out}")
    return 0


def load_documents(corpus_dir: Path) -> list[Document]:
    """Load documents from a materialized corpus snapshot."""
    path = corpus_dir / "documents.json"
    if not path.exists():
        raise FileNotFoundError(
            f"materialized corpus snapshot not found: {path}. "
            "Run with --fetch or materialize the raw corpus first."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Document.model_validate(item) for item in payload]


def make_doclets(documents: list[Document], *, max_chars: int) -> list[Document]:
    """Split documents into round-robin source-preserving doclets."""
    by_source: list[list[Document]] = []
    for document in documents:
        chunks = chunk_corpus([document], max_chars=max_chars)
        by_source.append(
            [
                Document(
                    id=f"{document.id}:doclet:{chunk.ordinal}",
                    title=f"{document.title} / doclet {chunk.ordinal}",
                    source=f"{document.source}#doclet:{chunk.ordinal}",
                    domain=document.domain,
                    text=chunk.text,
                    metadata={
                        **document.metadata,
                        "scale_doclet": True,
                        "parent_document_id": document.id,
                        "parent_source": document.source,
                        "doclet_ordinal": chunk.ordinal,
                    },
                )
                for chunk in chunks
            ]
        )
    doclets: list[Document] = []
    max_len = max((len(group) for group in by_source), default=0)
    for index in range(max_len):
        for group in by_source:
            if index < len(group):
                doclets.append(group[index])
    return doclets


def render_markdown(payload: dict[str, object], cells: list[SweepCell]) -> str:
    """Render the scale sweep as Markdown."""
    grouped: dict[str, list[SweepCell]] = defaultdict(list)
    for cell in cells:
        grouped[cell.strategy].append(cell)
    lines = [
        "# Tortus Scale Sweep Report",
        "",
        (
            "This report is a reproducible scale stress test over fetched public "
            "engineering-source text. The corpus is built by splitting real public pages "
            "from the Tortus manifest into source-preserving doclets. It is stronger than "
            "the toy demo, but it is still not a universal production superiority claim."
        ),
        "",
        "## Method",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Raw public sources in manifest: `{payload['raw_sources']}`",
        (
            f"- Raw public sources fetched this run: `{payload['raw_fetched']}` "
            "(cached snapshots are reused when this is `0`)"
        ),
        f"- Raw materialized documents: `{payload['raw_documents']}`",
        f"- Raw chunks at normal chunking: `{payload['raw_chunks']}`",
        f"- Doclet size: `{payload['doclet_chars']}` characters",
        f"- Max shared-phrase edges per phrase: `{payload['max_edges_per_phrase']}`",
        f"- Sweep sizes: `{', '.join(str(size) for size in payload['sizes'])}` documents",
        f"- Strategies: `{', '.join(str(strategy) for strategy in payload['strategies'])}`",
        f"- Python/platform: `{payload['python']}` on `{payload['platform']}`",
        f"- Total elapsed: `{float(payload['elapsed_seconds']):.1f}` seconds",
        "",
        "## Summary By Corpus Size",
        "",
        "| docs | strategy | pass | source | path | faith | p95 ms | fanout | portals | "
        "build s | eval s |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cell in cells:
        lines.append(
            "| "
            f"{cell.doc_count} | {cell.strategy} | {cell.pass_rate:.2f} | "
            f"{cell.source_recall:.2f} | {cell.path_recall:.2f} | "
            f"{cell.faithfulness:.2f} | {cell.p95_latency_ms:.1f} | "
            f"{cell.mean_shard_fanout:.1f} | {cell.mean_portal_hops:.1f} | "
            f"{cell.build_seconds:.1f} | {cell.eval_seconds:.1f} |"
        )
    lines.extend(["", "## Strategy Trend", ""])
    for strategy, rows in sorted(grouped.items()):
        ordered = sorted(rows, key=lambda cell: cell.doc_count)
        pass_values = ", ".join(f"{cell.doc_count}:{cell.pass_rate:.2f}" for cell in ordered)
        path_values = ", ".join(f"{cell.doc_count}:{cell.path_recall:.2f}" for cell in ordered)
        latency_values = ", ".join(
            f"{cell.doc_count}:{cell.p95_latency_ms:.1f}ms" for cell in ordered
        )
        lines.extend(
            [
                f"### `{strategy}`",
                "",
                f"- Pass rate by docs: {pass_values}",
                f"- Path recall by docs: {path_values}",
                f"- P95 latency by docs: {latency_values}",
                "",
            ]
        )
    lines.extend(
        [
            "## Caveats",
            "",
            "- The sweep uses public-source doclets, not a private enterprise corpus.",
            "- Labels are source/term/path heuristics tailored to the fetched public manifest.",
            "- Local hash embeddings are deterministic and reproducible, but not a substitute "
            "for reporting API embedding variability.",
            "- This run tests scale mechanics, latency, and relative retrieval behavior; "
            "larger audited corpora are still needed for a publication-grade claim.",
            "",
        ]
    )
    warnings = payload.get("warnings", [])
    if isinstance(warnings, list) and warnings:
        lines.extend(["## Fetch Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
