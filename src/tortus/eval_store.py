"""Persistence helpers for JSON and DuckDB eval reports."""

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from .eval import EvalReport


def write_eval_json(report: EvalReport, path: Path) -> None:
    """Write an evaluation report to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")


def write_eval_duckdb(report: EvalReport, path: Path) -> str:
    """Persist an evaluation report to a DuckDB results database."""
    path.parent.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S%fZ")
    with duckdb.connect(str(path)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS eval_runs (
                run_id TEXT PRIMARY KEY,
                suite TEXT NOT NULL,
                generated_at TIMESTAMP NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS eval_rows (
                run_id TEXT NOT NULL,
                question_id TEXT NOT NULL,
                suite TEXT NOT NULL,
                strategy TEXT NOT NULL,
                term_recall DOUBLE NOT NULL,
                source_recall DOUBLE NOT NULL,
                path_recall DOUBLE NOT NULL DEFAULT 0,
                path_precision DOUBLE NOT NULL DEFAULT 0,
                faithfulness DOUBLE NOT NULL DEFAULT 0,
                latency_ms DOUBLE NOT NULL,
                nodes_visited INTEGER NOT NULL,
                hops_taken INTEGER NOT NULL,
                portal_hops INTEGER NOT NULL DEFAULT 0,
                shard_fanout INTEGER NOT NULL,
                shard_crossings INTEGER NOT NULL DEFAULT 0,
                tokens_estimated INTEGER NOT NULL,
                path_edge_types TEXT NOT NULL DEFAULT '',
                expect_answer BOOLEAN NOT NULL DEFAULT TRUE,
                warnings TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "ALTER TABLE eval_rows ADD COLUMN IF NOT EXISTS path_recall DOUBLE DEFAULT 0"
        )
        connection.execute(
            "ALTER TABLE eval_rows ADD COLUMN IF NOT EXISTS path_edge_types TEXT DEFAULT ''"
        )
        connection.execute(
            "ALTER TABLE eval_rows ADD COLUMN IF NOT EXISTS path_precision DOUBLE DEFAULT 0"
        )
        connection.execute(
            "ALTER TABLE eval_rows ADD COLUMN IF NOT EXISTS faithfulness DOUBLE DEFAULT 0"
        )
        connection.execute(
            "ALTER TABLE eval_rows ADD COLUMN IF NOT EXISTS expect_answer BOOLEAN DEFAULT TRUE"
        )
        connection.execute(
            "ALTER TABLE eval_rows ADD COLUMN IF NOT EXISTS portal_hops INTEGER DEFAULT 0"
        )
        connection.execute(
            "ALTER TABLE eval_rows ADD COLUMN IF NOT EXISTS shard_crossings INTEGER DEFAULT 0"
        )
        connection.execute(
            "INSERT INTO eval_runs VALUES (?, ?, ?)",
            [run_id, report.suite, datetime.now(tz=UTC)],
        )
        connection.executemany(
            """
            INSERT INTO eval_rows (
                run_id,
                question_id,
                suite,
                strategy,
                term_recall,
                source_recall,
                path_recall,
                path_precision,
                faithfulness,
                latency_ms,
                nodes_visited,
                hops_taken,
                portal_hops,
                shard_fanout,
                shard_crossings,
                tokens_estimated,
                path_edge_types,
                expect_answer,
                warnings
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                [
                    run_id,
                    row.question_id,
                    row.suite,
                    row.strategy,
                    row.term_recall,
                    row.source_recall,
                    row.path_recall,
                    row.path_precision,
                    row.faithfulness,
                    row.latency_ms,
                    row.nodes_visited,
                    row.hops_taken,
                    row.portal_hops,
                    row.shard_fanout,
                    row.shard_crossings,
                    row.tokens_estimated,
                    ",".join(row.path_edge_types),
                    row.expect_answer,
                    "; ".join(row.warnings),
                ]
                for row in report.rows
            ],
        )
    return run_id
