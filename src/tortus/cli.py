"""Command-line interface for Tortus workflows."""

import json
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from .api import create_app
from .audit import export_audit_suite, import_audit_records
from .config import (
    PROJECT_CONFIG_NAME,
    default_project_config,
    get_settings,
    settings_with_overrides,
)
from .corpus_manifest import fetch_or_verify_public_corpus
from .eval import EvalReport, parse_strategies, questions_for_suite, run_eval
from .eval_store import write_eval_duckdb, write_eval_json
from .golden import write_candidate_golden_set
from .models import TraversalPolicy
from .pipeline import build_index, data_paths, ingest_builtin, ingest_sources, load_engine
from .release import run_doctor, run_release_check
from .report import generate_markdown_report

app = typer.Typer(help="Tortus: toroidal semantic graph retrieval.")
corpus_app = typer.Typer(help="Pinned public corpus workflows.")
audit_app = typer.Typer(help="Human audit import/export workflows.")
console = Console()
app.add_typer(corpus_app, name="corpus")
app.add_typer(audit_app, name="audit")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing tortus.toml."),
) -> None:
    """Initialize a local Tortus workspace."""
    config_path = Path(PROJECT_CONFIG_NAME)
    if config_path.exists() and not force:
        raise typer.BadParameter(
            f"{PROJECT_CONFIG_NAME} already exists; pass --force to replace it"
        )
    config_path.write_text(default_project_config(), encoding="utf-8")
    Path(".tortus/data").mkdir(parents=True, exist_ok=True)
    Path(".tortus/cache").mkdir(parents=True, exist_ok=True)
    console.print(f"initialized {config_path} and .tortus/")


@app.command()
def ingest(
    sources: Annotated[
        list[str] | None,
        typer.Argument(help="Files, directories, or URLs to ingest into the workspace corpus."),
    ] = None,
    corpus: str | None = typer.Option(None, help="Built-in corpus name to ingest."),
    manifest: Annotated[
        Path | None,
        typer.Option(help="TOML manifest containing sources to ingest."),
    ] = None,
    refresh: bool = typer.Option(False, "--refresh", help="Refetch URL sources."),
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Override TORTUS_DATA_DIR for this command."),
    ] = None,
) -> None:
    """Ingest built-in fixtures or user-provided workspace sources."""
    settings = settings_with_overrides(get_settings(), data_dir=data_dir)
    source_values = sources or []
    if source_values or manifest is not None:
        settings = settings_with_overrides(settings, corpus="workspace")
        result = ingest_sources(settings, source_values, manifest=manifest, refresh=refresh)
        console.print(f"Ingested {result.documents} documents and {result.chunks} chunks")
        console.print(f"snapshot={result.out_dir}")
        console.print(f"manifest={result.manifest_path}")
        for warning in result.warnings[:8]:
            console.print(f"[yellow]warning:[/yellow] {warning}")
        return

    active_corpus = corpus or settings.tortus_corpus
    if active_corpus == "workspace":
        raise typer.BadParameter("workspace ingestion requires sources or --manifest")
    settings = settings_with_overrides(settings, corpus=active_corpus)
    documents, chunks = ingest_builtin(settings, corpus=active_corpus)
    corpus_dir = data_paths(settings)["corpus"]
    console.print(f"Ingested {documents} documents and {chunks} chunks into {corpus_dir}")


@app.command()
def index(
    layout: str = typer.Option("torus", help="Layout to build: torus."),
    corpus: str | None = typer.Option(None, help="Corpus name to index."),
    embedding_provider: str | None = typer.Option(
        None,
        help="Override embedding provider: local, openai, or azure.",
    ),
    embedding_model: str | None = typer.Option(None, help="Override embedding model name."),
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Override TORTUS_DATA_DIR for this command."),
    ] = None,
) -> None:
    """Build index."""
    if layout != "torus":
        raise typer.BadParameter("only the torus layout is implemented in this release")
    settings = settings_with_overrides(
        get_settings(),
        corpus=corpus,
        data_dir=data_dir,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )
    stats = build_index(settings, corpus=settings.tortus_corpus)
    console.print("Built Tortus index")
    console.print_json(json.dumps(stats))


@app.command()
def query(
    text: str = typer.Argument(..., help="Question to ask Tortus."),
    explain: bool = typer.Option(False, "--explain", help="Print reasoning hops."),
    max_hops: int = typer.Option(3, help="Traversal hop budget."),
    local_only: bool = typer.Option(False, help="Disable portal hops."),
    corpus: str | None = typer.Option(None, help="Corpus name to query."),
    embedding_provider: str | None = typer.Option(
        None,
        help="Override embedding provider: local, openai, or azure.",
    ),
    embedding_model: str | None = typer.Option(None, help="Override embedding model name."),
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Override TORTUS_DATA_DIR for this command."),
    ] = None,
) -> None:
    """Run a query against the local Tortus engine."""
    settings = settings_with_overrides(
        get_settings(),
        corpus=corpus,
        data_dir=data_dir,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )
    engine = load_engine(settings)
    result = engine.answer(
        text,
        policy=TraversalPolicy(max_hops=max_hops, local_only=local_only, explain_hops=explain),
    )
    console.print(result.answer)
    console.print(f"confidence={result.confidence:.2f} nodes={result.budget.nodes_visited}")
    if result.warnings:
        console.print("[yellow]warnings:[/yellow] " + "; ".join(result.warnings))
    if explain:
        table = Table("from", "to", "edge", "weight", "score", "terms", "reason")
        for hop in result.reasoning_path[:20]:
            table.add_row(
                hop.from_node,
                hop.to_node,
                hop.edge_type.value,
                f"{hop.weight:.2f}",
                f"{hop.score:.2f}",
                ", ".join(hop.matched_terms),
                hop.reason,
            )
        console.print(table)


@app.command(name="eval")
def eval_command(
    suite: str = typer.Option("smoke", help="Eval suite: smoke."),
    strategies: str = typer.Option(
        "all",
        help="Comma-separated strategies, all, external, or all_with_external.",
    ),
    json_out: Annotated[
        Path | None,
        typer.Option(help="Optional path for JSON eval report."),
    ] = None,
    duckdb_out: Annotated[
        Path | None,
        typer.Option(help="Optional DuckDB path for eval rows."),
    ] = None,
    audit_file: Annotated[
        Path | None,
        typer.Option(help="Optional imported human-audit JSONL file to apply to labels."),
    ] = None,
    corpus: str | None = typer.Option(None, help="Corpus name to evaluate."),
    embedding_provider: str | None = typer.Option(
        None,
        help="Override embedding provider: local, openai, or azure.",
    ),
    embedding_model: str | None = typer.Option(None, help="Override embedding model name."),
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Override TORTUS_DATA_DIR for this command."),
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
    settings = settings_with_overrides(
        get_settings(),
        corpus=corpus,
        data_dir=data_dir,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )
    report = run_eval(
        load_engine(settings),
        suite=suite,
        strategies=selected_strategies,
        audit_file=audit_file,
    )
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
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate app creation without binding."),
) -> None:
    """Serve the GraphQL API and dashboard."""
    fastapi_app = create_app()
    if dry_run:
        console.print("Tortus app created successfully")
        console.print(f"routes={len(fastapi_app.routes)}")
        return
    uvicorn.run(fastapi_app, host=host, port=port)


@app.command()
def paths() -> None:
    """Print the active Tortus data paths."""
    for name, path in data_paths(get_settings()).items():
        console.print(f"{name}: {Path(path)}")


@app.command()
def doctor() -> None:
    """Check installed package assets, optional dependencies, and data paths."""
    table = Table("check", "ok", "detail")
    failed = False
    for check in run_doctor(get_settings()):
        failed = failed or not check.ok and not check.name.startswith("optional dependency")
        table.add_row(check.name, "yes" if check.ok else "no", check.detail)
    console.print(table)
    if failed:
        raise typer.Exit(code=1)


@app.command(name="release-check")
def release_check() -> None:
    """Build, inspect, install, and smoke-test release artifacts."""
    for message in run_release_check(Path.cwd()):
        console.print(message)


@corpus_app.command(name="fetch")
def corpus_fetch(
    fetch: bool = typer.Option(False, "--fetch", help="Fetch live public source snapshots."),
    refresh: bool = typer.Option(False, "--refresh", help="Refetch existing live snapshots."),
    materialize: bool = typer.Option(
        False,
        "--materialize",
        help="Write an indexable external corpus snapshot under TORTUS_DATA_DIR.",
    ),
    corpus_name: str = typer.Option(
        "external-engineering",
        "--corpus",
        help="Corpus name to materialize when --materialize is set.",
    ),
) -> None:
    """Verify or fetch the pinned public corpus manifest."""
    result = fetch_or_verify_public_corpus(
        get_settings(),
        fetch=fetch,
        refresh=refresh,
        materialize=materialize,
        corpus_name=corpus_name,
    )
    console.print(f"sources={result.sources} fetched={result.fetched}")
    console.print(f"manifest={result.out_path}")
    if result.corpus_path:
        console.print(
            f"corpus={result.corpus_path} documents={result.documents} chunks={result.chunks}"
        )
    for warning in result.warnings[:8]:
        console.print(f"[yellow]warning:[/yellow] {warning}")


@audit_app.command(name="export")
def audit_export(
    suite: str = typer.Option("golden100", help="Eval suite to export for audit."),
    out: Annotated[
        Path,
        typer.Option(help="Output JSONL audit path."),
    ] = Path("data/audits/golden100.audit.jsonl"),
) -> None:
    """Export benchmark labels for human audit."""
    count = export_audit_suite(suite, out)
    console.print(f"wrote_audit={out} rows={count}")


@audit_app.command(name="import")
def audit_import(
    path: Annotated[Path, typer.Argument(help="Reviewed JSONL audit file.")],
    out: Annotated[
        Path | None,
        typer.Option(help="Optional output path for validated audit records."),
    ] = None,
) -> None:
    """Validate and persist human-audited benchmark labels."""
    count = import_audit_records(path, out=out)
    console.print(f"imported_audit_rows={count}")
