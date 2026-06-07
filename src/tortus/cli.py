"""Command-line interface for Tortus workflows."""

from collections import Counter
from pathlib import Path
from typing import Annotated

import typer
import uvicorn
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
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
from .report import generate_markdown_report, strategy_summaries

app = typer.Typer(help="Tortus: toroidal semantic graph retrieval.")
corpus_app = typer.Typer(help="Pinned public corpus workflows.")
audit_app = typer.Typer(help="Human audit import/export workflows.")
console = Console()
app.add_typer(corpus_app, name="corpus")
app.add_typer(audit_app, name="audit")


def key_value_grid(rows: list[tuple[str, str]]) -> Table:
    """Build a compact key-value grid for terminal summaries."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="bold white", no_wrap=True)
    grid.add_column()
    for key, value in rows:
        grid.add_row(key, value)
    return grid


def print_summary_panel(
    title: str,
    rows: list[tuple[str, str]],
    *,
    style: str = "cyan",
    subtitle: str | None = None,
) -> None:
    """Print a titled summary panel."""
    console.print(
        Panel(
            key_value_grid(rows),
            title=f"[bold]{escape(title)}[/bold]",
            border_style=style,
            padding=(1, 2),
            subtitle=subtitle,
        )
    )


def print_message_panel(
    title: str,
    message: str,
    *,
    style: str = "cyan",
    subtitle: str | None = None,
) -> None:
    """Print a titled text panel."""
    console.print(
        Panel(
            message,
            title=f"[bold]{escape(title)}[/bold]",
            border_style=style,
            padding=(1, 2),
            subtitle=subtitle,
        )
    )


def print_next_steps(*steps: str) -> None:
    """Print concise next-step hints."""
    if not steps:
        return
    lines = "\n".join(
        f"[bold cyan]{index}.[/bold cyan] {step}" for index, step in enumerate(steps, 1)
    )
    print_message_panel("Next Steps", lines, style="blue")


def print_warnings(warnings: list[str]) -> None:
    """Print warnings in a consistent terminal panel."""
    if not warnings:
        return
    text = "\n".join(f"[yellow]{escape(warning)}[/yellow]" for warning in warnings[:8])
    if len(warnings) > 8:
        text += f"\n[dim]... {len(warnings) - 8} more warnings omitted[/dim]"
    print_message_panel("Warnings", text, style="yellow")


def styled_path(path: Path | str) -> str:
    """Return a path formatted for Rich output."""
    return f"[cyan]{escape(str(path))}[/cyan]"


def truncate_text(value: str, width: int = 110) -> str:
    """Return text clipped for compact terminal tables."""
    collapsed = " ".join(value.split())
    if len(collapsed) <= width:
        return collapsed
    return collapsed[: max(0, width - 3)] + "..."


def compact_identifier(value: str, width: int = 36) -> str:
    """Return a compact identifier that keeps both prefix and suffix context."""
    collapsed = " ".join(value.split())
    if len(collapsed) <= width:
        return collapsed
    prefix = max(6, width - 12)
    return f"{collapsed[:prefix]}...{collapsed[-8:]}"


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
    print_summary_panel(
        "Tortus Workspace Ready",
        [
            ("Config", styled_path(config_path)),
            ("Data", styled_path(".tortus/data")),
            ("Cache", styled_path(".tortus/cache")),
        ],
        style="green",
    )
    print_next_steps(
        "[bold]tortus ingest ./docs[/bold] to snapshot your documents",
        "[bold]tortus index[/bold] to build the graph",
        "[bold]tortus query \"your question\" --explain[/bold] to inspect retrieval",
    )


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
        with console.status("[bold cyan]Snapshotting workspace sources...[/bold cyan]"):
            result = ingest_sources(settings, source_values, manifest=manifest, refresh=refresh)
        print_summary_panel(
            "Workspace Ingest Complete",
            [
                ("Documents", f"[bold green]{result.documents}[/bold green]"),
                ("Chunks", f"[bold green]{result.chunks}[/bold green]"),
                ("Snapshot", styled_path(result.out_dir)),
                ("Manifest", styled_path(result.manifest_path)),
            ],
            style="green",
        )
        print_warnings(result.warnings)
        print_next_steps("[bold]tortus index[/bold] to build the graph for this snapshot")
        return

    active_corpus = corpus or settings.tortus_corpus
    if active_corpus == "workspace":
        raise typer.BadParameter("workspace ingestion requires sources or --manifest")
    settings = settings_with_overrides(settings, corpus=active_corpus)
    with console.status(f"[bold cyan]Preparing corpus {escape(active_corpus)}...[/bold cyan]"):
        documents, chunks = ingest_builtin(settings, corpus=active_corpus)
    corpus_dir = data_paths(settings)["corpus"]
    print_summary_panel(
        "Corpus Ingest Complete",
        [
            ("Corpus", f"[bold]{escape(active_corpus)}[/bold]"),
            ("Documents", f"[bold green]{documents}[/bold green]"),
            ("Chunks", f"[bold green]{chunks}[/bold green]"),
            ("Output", styled_path(corpus_dir)),
        ],
        style="green",
    )
    print_next_steps(
        f"[bold]tortus index --corpus {escape(active_corpus)}[/bold] to build the graph"
    )


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
    with console.status(
        f"[bold cyan]Building {escape(settings.tortus_corpus)} graph index...[/bold cyan]"
    ):
        stats = build_index(settings, corpus=settings.tortus_corpus)
    print_summary_panel(
        "Tortus Index Built",
        [
            ("Corpus", f"[bold]{escape(settings.tortus_corpus)}[/bold]"),
            ("Layout", f"[bold]{escape(layout)}[/bold]"),
            ("Embedding", f"{escape(settings.tortus_embedding_provider)}"),
            ("Nodes", f"[bold green]{stats['nodes']}[/bold green]"),
            ("Edges", f"[bold green]{stats['edges']}[/bold green]"),
            ("Portal edges", f"[bold green]{stats['portal_edges']}[/bold green]"),
            ("Schema", str(stats["schema_version"])),
        ],
        style="green",
    )
    print_next_steps(
        "[bold]tortus query \"your question\" --explain[/bold] to inspect retrieval",
        "[bold]tortus serve[/bold] to open the diagnostic workbench",
    )


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
    with console.status("[bold cyan]Loading Tortus engine...[/bold cyan]"):
        engine = load_engine(settings)
    with console.status("[bold cyan]Traversing graph and grounding answer...[/bold cyan]"):
        result = engine.answer(
            text,
            policy=TraversalPolicy(max_hops=max_hops, local_only=local_only, explain_hops=explain),
        )

    confidence_style = "green" if result.confidence >= 0.65 else "yellow"
    print_message_panel(
        "Answer",
        escape(result.answer.strip() or "No answer text returned."),
        style=confidence_style,
        subtitle=(
            f"confidence {result.confidence:.2f} | nodes {result.budget.nodes_visited} | "
            f"hops {result.budget.hops_taken} | portals {result.budget.portal_hops}"
        ),
    )
    print_summary_panel(
        "Retrieval Snapshot",
        [
            ("Corpus", f"[bold]{escape(settings.tortus_corpus)}[/bold]"),
            ("Evidence spans", f"[bold green]{len(result.evidence)}[/bold green]"),
            ("Shard fanout", str(result.budget.shard_fanout)),
            ("Shard crossings", str(result.budget.shard_crossings)),
            ("Tokens estimated", str(result.budget.tokens_estimated)),
            ("Unsupported claims", str(len(result.trace.unsupported_claims))),
        ],
        style="cyan",
    )
    if result.evidence:
        evidence_table = Table(
            title="Evidence",
            box=box.SIMPLE_HEAVY,
            header_style="bold cyan",
            show_lines=False,
            expand=True,
        )
        evidence_table.add_column("source", no_wrap=True)
        evidence_table.add_column("range", justify="right", no_wrap=True)
        evidence_table.add_column("span", overflow="fold")
        for span in result.evidence[:6]:
            evidence_table.add_row(
                escape(compact_identifier(span.uri, 34)),
                f"{span.start}-{span.end}",
                escape(truncate_text(span.text, 120)),
            )
        console.print(evidence_table)
    print_warnings(result.warnings)
    if explain:
        table = Table(
            title="Reasoning Path",
            box=box.SIMPLE_HEAVY,
            header_style="bold cyan",
            show_lines=False,
            expand=True,
        )
        table.add_column("#", justify="right", no_wrap=True)
        table.add_column("path", overflow="fold")
        table.add_column("edge", no_wrap=True)
        table.add_column("score", justify="right")
        table.add_column("why", overflow="fold")
        for index, hop in enumerate(result.reasoning_path[:20], 1):
            path = (
                f"{compact_identifier(hop.from_node, 14)} -> "
                f"{compact_identifier(hop.to_node, 14)}"
            )
            terms = truncate_text(", ".join(hop.matched_terms), 40)
            why = hop.reason if not terms else f"{terms} | {hop.reason}"
            table.add_row(
                str(index),
                escape(path),
                hop.edge_type.value,
                f"{hop.score:.2f}",
                escape(truncate_text(why, 72)),
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
    show_rows: bool = typer.Option(False, "--rows", help="Print the row-level eval table."),
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
    with console.status(
        f"[bold cyan]Running {escape(suite)} eval across "
        f"{len(selected_strategies)} strategies...[/bold cyan]"
    ):
        report = run_eval(
            load_engine(settings),
            suite=suite,
            strategies=selected_strategies,
            audit_file=audit_file,
        )
    audit_counts = Counter(row.audit_status for row in report.rows)
    print_summary_panel(
        "Evaluation Complete",
        [
            ("Suite", f"[bold]{escape(suite)}[/bold]"),
            ("Rows", f"[bold green]{len(report.rows)}[/bold green]"),
            ("Strategies", str(len(report.strategies()))),
            ("Corpus", f"[bold]{escape(settings.tortus_corpus)}[/bold]"),
            (
                "Audit status",
                ", ".join(
                    f"{escape(status)}={count}" for status, count in sorted(audit_counts.items())
                ),
            ),
        ],
        style="green",
    )

    summary_table = Table(
        title="Strategy Summary",
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
        expand=True,
    )
    summary_table.add_column("strategy", no_wrap=True)
    summary_table.add_column("pass", justify="right")
    summary_table.add_column("src", justify="right")
    summary_table.add_column("path", justify="right")
    summary_table.add_column("prec", justify="right")
    summary_table.add_column("faith", justify="right")
    summary_table.add_column("p95 ms", justify="right")
    summary_table.add_column("fanout", justify="right")
    summary_table.add_column("skip", justify="right")
    for summary in strategy_summaries(report):
        style = "dim" if summary.skipped_rate >= 1.0 else None
        if summary.strategy == "tortus_torus":
            style = "bold cyan"
        summary_table.add_row(
            summary.strategy,
            f"{summary.pass_rate:.2f}",
            f"{summary.source_recall:.2f}",
            f"{summary.path_recall:.2f}",
            f"{summary.path_precision:.2f}",
            f"{summary.faithfulness:.2f}",
            f"{summary.p95_latency_ms:.1f}",
            f"{summary.mean_shard_fanout:.1f}",
            f"{summary.skipped_rate:.2f}",
            style=style,
        )
    console.print(summary_table)

    if show_rows:
        table = Table(
            title="Eval Rows",
            box=box.SIMPLE_HEAVY,
            header_style="bold cyan",
            expand=True,
        )
        for column in (
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
        ):
            table.add_column(column, overflow="fold")
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
    if json_out:
        write_eval_json(report, json_out)
        print_summary_panel("JSON Report Written", [("Path", styled_path(json_out))], style="green")
    if duckdb_out:
        run_id = write_eval_duckdb(report, duckdb_out)
        print_summary_panel(
            "DuckDB Report Written",
            [("Path", styled_path(duckdb_out)), ("Run ID", f"[dim]{escape(run_id)}[/dim]")],
            style="green",
        )


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
    print_summary_panel(
        "Markdown Report Written",
        [
            ("Input", styled_path(eval_json)),
            ("Output", styled_path(out)),
            ("Rows", str(len(report.rows))),
        ],
        style="green",
    )


@app.command(name="golden-set")
def golden_set_command(
    out: Annotated[
        Path,
        typer.Option(help="Output JSON path for curated golden questions."),
    ] = Path("data/golden_set.json"),
    count: int = typer.Option(100, help="Number of candidate questions to generate."),
) -> None:
    """Generate the deterministic curated golden set."""
    with console.status("[bold cyan]Generating candidate golden set...[/bold cyan]"):
        write_candidate_golden_set(out, count=count)
    print_summary_panel(
        "Golden Set Written",
        [("Path", styled_path(out)), ("Questions", f"[bold green]{count}[/bold green]")],
        style="green",
    )


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host to bind."),
    port: int = typer.Option(8000, help="Port to bind."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate app creation without binding."),
) -> None:
    """Serve the GraphQL API and dashboard."""
    fastapi_app = create_app()
    if dry_run:
        print_summary_panel(
            "Server Dry Run Passed",
            [("Routes", f"[bold green]{len(fastapi_app.routes)}[/bold green]")],
            style="green",
        )
        return
    print_summary_panel(
        "Starting Tortus Server",
        [
            ("API", f"[cyan]http://{escape(host)}:{port}/graphql[/cyan]"),
            ("Dashboard", f"[cyan]http://{escape(host)}:{port}/[/cyan]"),
        ],
        style="cyan",
    )
    uvicorn.run(fastapi_app, host=host, port=port)


@app.command()
def paths() -> None:
    """Print the active Tortus data paths."""
    print_summary_panel(
        "Active Data Paths",
        [(name, styled_path(Path(path))) for name, path in data_paths(get_settings()).items()],
        style="cyan",
    )


@app.command()
def doctor() -> None:
    """Check installed package assets, optional dependencies, and data paths."""
    table = Table(
        title="Doctor Checks",
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("check", overflow="fold")
    table.add_column("status", no_wrap=True)
    table.add_column("detail", overflow="fold")
    failed = False
    for check in run_doctor(get_settings()):
        failed = failed or not check.ok and not check.name.startswith("optional dependency")
        status = "[green]ok[/green]" if check.ok else "[yellow]missing[/yellow]"
        if not check.ok and not check.name.startswith("optional dependency"):
            status = "[red]fail[/red]"
        table.add_row(check.name, status, escape(check.detail))
    console.print(table)
    if failed:
        print_message_panel("Doctor Failed", "A required check failed.", style="red")
    else:
        print_message_panel(
            "Doctor Passed",
            "Required package assets and runtime paths are available.",
            style="green",
        )
    if failed:
        raise typer.Exit(code=1)


@app.command(name="release-check")
def release_check() -> None:
    """Build, inspect, install, and smoke-test release artifacts."""
    messages: list[str] = []
    with console.status("[bold cyan]Running release checks...[/bold cyan]"):
        messages = list(run_release_check(Path.cwd()))
    print_message_panel(
        "Release Check Passed",
        "\n".join(f"[green]{escape(message)}[/green]" for message in messages),
        style="green",
    )


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
    rows = [
        ("Sources", f"[bold green]{result.sources}[/bold green]"),
        ("Fetched", f"[bold green]{result.fetched}[/bold green]"),
        ("Manifest", styled_path(result.out_path)),
    ]
    if result.corpus_path:
        rows.extend(
            [
                ("Corpus", styled_path(result.corpus_path)),
                ("Documents", f"[bold green]{result.documents}[/bold green]"),
                ("Chunks", f"[bold green]{result.chunks}[/bold green]"),
            ]
        )
    print_summary_panel("Public Corpus Snapshot", rows, style="green")
    print_warnings(result.warnings)


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
    print_summary_panel(
        "Audit File Exported",
        [
            ("Suite", f"[bold]{escape(suite)}[/bold]"),
            ("Rows", f"[bold green]{count}[/bold green]"),
            ("Path", styled_path(out)),
        ],
        style="green",
    )


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
    print_summary_panel(
        "Audit File Imported",
        [
            ("Rows", f"[bold green]{count}[/bold green]"),
            ("Source", styled_path(path)),
            ("Output", styled_path(out or Path("data/audits") / f"{path.stem}.imported.jsonl")),
        ],
        style="green",
    )
