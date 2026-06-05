"""Command-line interface for Tortus workflows."""

import json
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .api import create_app
from .config import get_settings
from .eval import EvalReport, parse_strategies, questions_for_suite, run_eval
from .eval_store import write_eval_duckdb, write_eval_json
from .golden import write_candidate_golden_set
from .models import TraversalPolicy
from .pipeline import build_index, data_paths, ingest_builtin, load_engine
from .report import generate_markdown_report

app = typer.Typer(help="Tortus: toroidal semantic graph retrieval.")
console = Console()


@app.command()
def ingest(corpus: str | None = typer.Option(None, help="Corpus name to ingest.")) -> None:
    """Ingest a built-in corpus snapshot."""
    settings = get_settings()
    documents, chunks = ingest_builtin(settings, corpus=corpus)
    corpus_dir = data_paths(settings)["corpus"]
    console.print(f"Ingested {documents} documents and {chunks} chunks into {corpus_dir}")


@app.command()
def index(
    layout: str = typer.Option("torus", help="Layout to build: torus."),
    corpus: str | None = typer.Option(None, help="Corpus name to index."),
) -> None:
    """Build index."""
    if layout != "torus":
        raise typer.BadParameter("only the torus layout is implemented in v1")
    settings = get_settings()
    stats = build_index(settings, corpus=corpus)
    console.print("Built Tortus index")
    console.print_json(json.dumps(stats))


@app.command()
def query(
    text: str = typer.Argument(..., help="Question to ask Tortus."),
    explain: bool = typer.Option(False, "--explain", help="Print reasoning hops."),
    max_hops: int = typer.Option(3, help="Traversal hop budget."),
    local_only: bool = typer.Option(False, help="Disable portal hops."),
) -> None:
    """Run a query against the local Tortus engine."""
    engine = load_engine(get_settings())
    result = engine.answer(
        text,
        policy=TraversalPolicy(max_hops=max_hops, local_only=local_only, explain_hops=explain),
    )
    console.print(result.answer)
    console.print(f"confidence={result.confidence:.2f} nodes={result.budget.nodes_visited}")
    if result.warnings:
        console.print("[yellow]warnings:[/yellow] " + "; ".join(result.warnings))
    if explain:
        table = Table("from", "to", "edge", "weight")
        for hop in result.reasoning_path[:20]:
            table.add_row(hop.from_node, hop.to_node, hop.edge_type.value, f"{hop.weight:.2f}")
        console.print(table)


@app.command(name="eval")
def eval_command(
    suite: str = typer.Option("smoke", help="Eval suite: smoke."),
    strategies: str = typer.Option(
        "all",
        help="Comma-separated strategies or all.",
    ),
    json_out: Annotated[
        Path | None,
        typer.Option(help="Optional path for JSON eval report."),
    ] = None,
    duckdb_out: Annotated[
        Path | None,
        typer.Option(help="Optional DuckDB path for eval rows."),
    ] = None,
) -> None:
    """Run an evaluation suite."""
    try:
        questions_for_suite(suite)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    try:
        selected_strategies = parse_strategies(strategies)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    report = run_eval(load_engine(get_settings()), suite=suite, strategies=selected_strategies)
    table = Table(
        "question",
        "suite",
        "strategy",
        "term",
        "source",
        "path",
        "latency_ms",
        "nodes",
        "hops",
        "portals",
        "fanout",
        "cross",
        "tokens",
    )
    for row in report.rows:
        table.add_row(
            row.question_id,
            row.suite,
            row.strategy,
            f"{row.term_recall:.2f}",
            f"{row.source_recall:.2f}",
            f"{row.path_recall:.2f}",
            f"{row.latency_ms:.1f}",
            str(row.nodes_visited),
            str(row.hops_taken),
            str(row.portal_hops),
            str(row.shard_fanout),
            str(row.shard_crossings),
            str(row.tokens_estimated),
        )
    console.print(table)
    for strategy in report.strategies():
        console.print(f"{strategy}_pass_rate={report.pass_rate(strategy):.2f}")
    if json_out:
        write_eval_json(report, json_out)
        console.print(f"wrote_json={json_out}")
    if duckdb_out:
        run_id = write_eval_duckdb(report, duckdb_out)
        console.print(f"wrote_duckdb={duckdb_out} run_id={run_id}")


@app.command(name="report")
def report_command(
    eval_json: Annotated[
        Path,
        typer.Option(help="Input JSON eval report."),
    ] = Path("data/eval/full.json"),
    out: Annotated[
        Path,
        typer.Option(help="Output markdown report."),
    ] = Path("data/reports/eval-report.md"),
) -> None:
    """Generate a markdown report from an eval JSON file."""
    if not eval_json.exists():
        raise typer.BadParameter(f"eval report does not exist: {eval_json}")
    report = EvalReport.model_validate_json(eval_json.read_text(encoding="utf-8"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(generate_markdown_report(report), encoding="utf-8")
    console.print(f"wrote_report={out}")


@app.command(name="golden-set")
def golden_set_command(
    out: Annotated[
        Path,
        typer.Option(help="Output JSON path for curated golden questions."),
    ] = Path("data/golden_set.json"),
    count: int = typer.Option(100, help="Number of candidate questions to generate."),
) -> None:
    """Generate the deterministic curated golden set."""
    write_candidate_golden_set(out, count=count)
    console.print(f"wrote_golden_set={out} count={count}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind."),
    port: int = typer.Option(8000, help="Port to bind."),
) -> None:
    """Serve the GraphQL API and dashboard."""
    uvicorn.run(create_app(), host=host, port=port)


@app.command()
def paths() -> None:
    """Print the active Tortus data paths."""
    for name, path in data_paths(get_settings()).items():
        console.print(f"{name}: {Path(path)}")
