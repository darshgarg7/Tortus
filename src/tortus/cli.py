"""Command-line interface for Tortus workflows."""

import json
import re
import webbrowser
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich import box
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from .audit import export_audit_suite, import_audit_records
from .config import (
    PROJECT_CONFIG_NAME,
    USER_CONFIG_PATH,
    Settings,
    default_project_config,
    get_settings,
    settings_with_overrides,
    user_config_values,
)
from .corpus_manifest import fetch_or_verify_public_corpus
from .eval import EvalReport, parse_strategies, questions_for_suite, run_eval
from .eval_store import write_eval_duckdb, write_eval_json
from .golden import write_candidate_golden_set
from .models import AnswerResult, SourceHealth, TraversalPolicy
from .pipeline import build_index, data_paths, ingest_builtin, ingest_sources, load_engine
from .release import run_doctor, run_release_check
from .report import generate_markdown_report, strategy_summaries

app = typer.Typer(help="Tortus: toroidal semantic graph retrieval.")
corpus_app = typer.Typer(help="Pinned public corpus workflows.")
audit_app = typer.Typer(help="Human audit import/export workflows.")
console = Console()
app.add_typer(corpus_app, name="corpus")
app.add_typer(audit_app, name="audit")

DEFAULT_DEMO_CORPUS = "acme-payments-demo"
DEFAULT_DEMO_QUERY = "What should Acme fix to stop EU refund trace fragmentation?"
TORTUS_HOME = Path.home() / ".tortus"
TORTUS_PROJECTS_DIR = TORTUS_HOME / "projects"
LAST_PROJECT_PATH = TORTUS_HOME / "last_project.json"


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


def print_quality_notice(quality_mode: str, fallback_warnings: list[str]) -> None:
    """Print a prominent quality-mode notice BEFORE the diagnosis when no LLM key is set."""
    if not fallback_warnings:
        return
    console.print(
        Panel(
            "[yellow]Running in [bold]local extraction mode[/bold] — no API key is configured.\n"
            "Extraction and synthesis use deterministic heuristics. The diagnosis below is\n"
            "grounded in cited evidence but is not LLM-polished.\n\n"
            "To enable full quality: [bold cyan]tortus setup --provider openai[/bold cyan]",
            title="[bold yellow]\u26a0  Quality: Local Mode[/bold yellow]",
            border_style="yellow",
            padding=(1, 2),
        )
    )


def _readable_step(step: str) -> str:
    """Return a human-readable label for an evidence path step, stripping raw URI schemes."""
    if "://" in step:
        tail = step.rstrip("/").rsplit("/", 1)[-1]
        label = tail.replace("-", " ").replace("_", " ").strip()
        return f"[source] {label}" if label else step
    return step


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


def load_api_runtime() -> tuple[Callable[..., Any], Any]:
    """Load optional dashboard/API dependencies or exit with an install hint."""
    try:
        import uvicorn

        from .api import create_app
    except ImportError as exc:
        package_install = escape('pip install "tortus-rag[api]"')
        editable_install = escape('python -m pip install -e ".[api]"')
        print_message_panel(
            "API Extra Required",
            "Dashboard/API commands need the optional API extra.\n\n"
            "[bold]Installed package:[/bold]\n"
            f"[bold cyan]{package_install}[/bold cyan]\n\n"
            "[bold]Working from this repo:[/bold]\n"
            f"[bold cyan]{editable_install}[/bold cyan]\n\n"
            "[bold]Then retry:[/bold]\n"
            "[bold cyan]tortus serve --dry-run[/bold cyan]",
            style="yellow",
        )
        raise typer.Exit(code=1) from exc
    return create_app, uvicorn


def slugify(value: str, fallback: str = "project") -> str:
    """Return a stable filesystem-safe project slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or fallback)[:64]


def default_solve_project(query: str, sources: list[str], *, demo: bool) -> str:
    """Return the default hidden project name for a solve run."""
    if demo:
        return "acme-demo"
    seed = sources[0] if sources else query
    return slugify(Path(seed).stem if not seed.startswith("http") else seed, fallback="workspace")


def project_data_dir(project: str) -> Path:
    """Return the hidden data directory for a named Tortus project."""
    return TORTUS_PROJECTS_DIR / slugify(project) / "data"


def project_cache_dir() -> Path:
    """Return the shared per-user Tortus cache directory."""
    return TORTUS_HOME / "cache"


def settings_for_solve_project(project: str, corpus: str) -> Settings:
    """Return settings with user-level project paths hidden from the CLI."""
    return settings_with_overrides(
        get_settings(),
        corpus=corpus,
        data_dir=project_data_dir(project),
        cache_dir=project_cache_dir(),
    )


def write_last_project(*, project: str, data_dir: Path, corpus: str) -> None:
    """Persist the last solve project for serve/open helpers."""
    TORTUS_HOME.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "project": project,
        "data_dir": str(data_dir),
        "corpus": corpus,
        "updated_at": datetime.now(tz=UTC).isoformat(),
    }
    LAST_PROJECT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def last_project_settings() -> Settings:
    """Return settings for the last solve project."""
    if not LAST_PROJECT_PATH.exists():
        raise typer.BadParameter("no last Tortus project found; run tortus solve or tortus demo")
    payload = json.loads(LAST_PROJECT_PATH.read_text(encoding="utf-8"))
    return settings_with_overrides(
        get_settings(),
        corpus=str(payload.get("corpus", "workspace")),
        data_dir=Path(str(payload.get("data_dir", project_data_dir("workspace")))),
        cache_dir=project_cache_dir(),
    )


def toml_string(value: str) -> str:
    """Return a TOML-safe quoted string."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def write_user_config(updates: dict[str, str]) -> None:
    """Write user-level Tortus settings without touching repo files."""
    values = {key: str(value) for key, value in user_config_values().items() if value is not None}
    values.update(updates)
    key_order = [
        "openai_api_key",
        "openai_base_url",
        "azure_openai_endpoint",
        "azure_openai_api_key",
        "azure_openai_deployment",
        "azure_openai_api_version",
        "azure_openai_embedding_deployment",
        "tortus_llm_model",
        "tortus_extraction_provider",
        "tortus_synthesis_provider",
        "tortus_embedding_provider",
        "tortus_embedding_model",
    ]
    field_to_key = {
        "tortus_llm_model": "llm_model",
        "tortus_extraction_provider": "extraction_provider",
        "tortus_synthesis_provider": "synthesis_provider",
        "tortus_embedding_provider": "embedding_provider",
        "tortus_embedding_model": "embedding_model",
    }
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[tortus]"]
    for field in key_order:
        value = values.get(field)
        if value:
            lines.append(f"{field_to_key.get(field, field)} = {toml_string(value)}")
    lines.append("")
    USER_CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")
    get_settings.cache_clear()


def has_llm_key(settings: Settings) -> bool:
    """Return whether settings include OpenAI or Azure chat credentials."""
    return bool(
        settings.openai_api_key
        or (
            settings.azure_openai_endpoint
            and settings.azure_openai_api_key
            and settings.azure_openai_deployment
        )
    )


def warn_or_confirm_local_quality(
    settings: Settings,
    *,
    project: str,
    corpus: str,
    yes: bool,
) -> tuple[list[str], Settings]:
    """Warn about local fallback when no LLM key is configured."""
    if has_llm_key(settings):
        return [], settings
    message = (
        "No OpenAI/Azure key is configured. Tortus will run with deterministic local "
        "extraction and synthesis, which is useful for demos but rougher on messy docs."
    )
    if console.is_interactive and not yes:
        console.print(f"[yellow]{escape(message)}[/yellow]")
        if not typer.confirm("Continue with local fallback?", default=True):
            if typer.confirm("Would you like to configure your API key now?", default=True):
                provider = typer.prompt("Select provider (openai or azure)", default="openai")
                try:
                    setup(provider=provider)
                    get_settings.cache_clear()
                    new_settings = settings_for_solve_project(project, corpus)
                    console.print(
                        "[bold green]API key configured successfully. "
                        "Running in high-quality LLM mode![/bold green]\n"
                    )
                    return [], new_settings
                except Exception as e:
                    console.print(f"[red]Configuration failed: {e}[/red]")
                    raise typer.Exit(code=1) from e
            raise typer.Exit(code=1)
    return [message], settings


def print_source_health_result(source_health: SourceHealth) -> None:
    """Print source-health telemetry in a compact panel."""
    rows = [
        ("Documents", str(source_health.documents)),
        ("Chunks", str(source_health.chunks)),
        ("Supported sources", str(source_health.supported_sources)),
        ("Unsupported sources", str(source_health.unsupported_sources)),
        ("Empty documents", str(source_health.empty_documents)),
        ("Duplicate documents", str(source_health.duplicate_documents)),
        ("Quality score", f"{source_health.quality_score:.2f}"),
    ]
    print_summary_panel("Source Health", rows, style="cyan")
    print_warnings(source_health.warnings)


def print_action_plan(result: AnswerResult) -> None:
    """Print the user-facing diagnosis, path, actions, and missing evidence."""
    diagnosis_text = result.diagnosis or result.answer
    quality_label = (
        "local | tortus setup to upgrade"
        if result.quality_mode == "deterministic-local"
        else result.quality_mode
    )
    print_message_panel(
        "Diagnosis",
        escape(diagnosis_text),
        style="green" if result.confidence >= 0.65 else "yellow",
        subtitle=f"confidence {result.confidence:.2f} | quality {escape(quality_label)}",
    )
    path = result.root_cause_path
    readable_path = [_readable_step(str(step)) for step in path]
    if readable_path:
        path_table = Table(title="Likely Evidence Path", box=box.SIMPLE_HEAVY, expand=True)
        path_table.add_column("#", justify="right", no_wrap=True)
        path_table.add_column("step", overflow="fold")
        for index, step in enumerate(readable_path[:8], 1):
            path_table.add_row(str(index), escape(step))
        console.print(path_table)

    actions = result.recommended_actions
    if actions:
        action_table = Table(title="Recommended Actions", box=box.SIMPLE_HEAVY, expand=True)
        action_table.add_column("#", justify="right", no_wrap=True)
        action_table.add_column("action", overflow="fold")
        for index, action in enumerate(actions[:8], 1):
            action_table.add_row(str(index), escape(str(action)))
        console.print(action_table)

    missing = result.missing_evidence
    if missing:
        print_message_panel(
            "Missing Evidence",
            "\n".join(f"- {escape(str(item))}" for item in missing[:8]),
            style="yellow",
        )


def solve_result_markdown(query_text: str, result: AnswerResult) -> str:
    """Render a solve result as a ticket-ready Markdown report."""
    lines = [
        "# Tortus Solve Report",
        "",
        f"**Question:** {query_text}",
        "",
        "## Diagnosis",
        "",
        result.diagnosis or result.answer,
        "",
        "## Recommended Actions",
        "",
    ]
    if result.recommended_actions:
        lines.extend(
            f"{index}. {action}"
            for index, action in enumerate(result.recommended_actions, 1)
        )
    else:
        lines.append("No recommended actions were generated.")
    lines.extend(["", "## Evidence Path", ""])
    if result.root_cause_path:
        lines.extend(
            f"{index}. {_readable_step(str(step))}"
            for index, step in enumerate(result.root_cause_path, 1)
        )
    else:
        lines.append("No evidence path was selected.")
    lines.extend(["", "## Citations", ""])
    if result.citations:
        for index, span in enumerate(result.citations, 1):
            lines.extend(
                [
                    f"{index}. `{span.uri}` `{span.start}-{span.end}`",
                    "",
                    f"   {span.text}",
                    "",
                ]
            )
    else:
        lines.append("No citations were selected.")
    lines.extend(
        [
            "",
            "## Source Health",
            "",
            f"- Documents: {result.source_health.documents}",
            f"- Chunks: {result.source_health.chunks}",
            f"- Unsupported sources: {result.source_health.unsupported_sources}",
            f"- Empty documents: {result.source_health.empty_documents}",
            f"- Duplicate documents: {result.source_health.duplicate_documents}",
            f"- Quality score: {result.source_health.quality_score:.2f}",
            "",
            "## Missing Evidence",
            "",
        ]
    )
    if result.missing_evidence:
        lines.extend(f"- {item}" for item in result.missing_evidence)
    else:
        lines.append("No missing-evidence warnings were generated.")
    lines.extend(
        [
            "",
            "## Run Metadata",
            "",
            f"- Confidence: {result.confidence:.2f}",
            f"- Quality mode: {result.quality_mode}",
            f"- Nodes visited: {result.budget.nodes_visited}",
            f"- Hops taken: {result.budget.hops_taken}",
            f"- Portal hops: {result.budget.portal_hops}",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


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
    """Build the toroidal graph, vector index, and portal edges for the active corpus."""
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


@app.command()
def setup(
    provider: str = typer.Option("openai", help="Provider to configure: openai or azure."),
    openai_api_key: str | None = typer.Option(None, help="OpenAI API key to store locally."),
    openai_base_url: str | None = typer.Option(None, help="Optional OpenAI-compatible base URL."),
    azure_endpoint: str | None = typer.Option(None, help="Azure OpenAI endpoint."),
    azure_api_key: str | None = typer.Option(None, help="Azure OpenAI API key."),
    azure_deployment: str | None = typer.Option(None, help="Azure OpenAI chat deployment."),
    azure_embedding_deployment: str | None = typer.Option(
        None,
        help="Optional Azure OpenAI embedding deployment.",
    ),
    azure_api_version: str = typer.Option(
        "2025-01-01-preview",
        help="Azure OpenAI API version.",
    ),
) -> None:
    """Configure per-user Tortus API credentials outside the repo."""
    normalized_provider = provider.strip().lower()
    updates: dict[str, str] = {
        "tortus_extraction_provider": "auto",
        "tortus_synthesis_provider": "auto",
    }
    if normalized_provider == "openai":
        key = openai_api_key
        if key is None and console.is_interactive:
            key = typer.prompt("OPENAI_API_KEY", hide_input=True)
        if not key:
            raise typer.BadParameter("OPENAI_API_KEY is required for provider=openai")
        updates["openai_api_key"] = key
        if openai_base_url:
            updates["openai_base_url"] = openai_base_url
    elif normalized_provider == "azure":
        endpoint = azure_endpoint
        key = azure_api_key
        deployment = azure_deployment
        if endpoint is None and console.is_interactive:
            endpoint = typer.prompt("AZURE_OPENAI_ENDPOINT")
        if key is None and console.is_interactive:
            key = typer.prompt("AZURE_OPENAI_API_KEY", hide_input=True)
        if deployment is None and console.is_interactive:
            deployment = typer.prompt("AZURE_OPENAI_DEPLOYMENT")
        if not endpoint or not key or not deployment:
            raise typer.BadParameter(
                "AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and "
                "AZURE_OPENAI_DEPLOYMENT are required for provider=azure"
            )
        updates.update(
            {
                "azure_openai_endpoint": endpoint,
                "azure_openai_api_key": key,
                "azure_openai_deployment": deployment,
                "azure_openai_api_version": azure_api_version,
            }
        )
        if azure_embedding_deployment:
            updates["azure_openai_embedding_deployment"] = azure_embedding_deployment
    else:
        raise typer.BadParameter("provider must be openai or azure")
    write_user_config(updates)
    print_summary_panel(
        "Tortus User Configured",
        [
            ("Provider", f"[bold green]{escape(normalized_provider)}[/bold green]"),
            ("Config", styled_path(USER_CONFIG_PATH)),
            ("Secrets", "stored locally, outside this repository"),
        ],
        style="green",
    )
    print_next_steps(
        '[bold]tortus solve "What happened and what should I fix?" ./docs[/bold]'
    )


@app.command()
def solve(
    query_text: Annotated[str, typer.Argument(help="Problem or question to solve.")],
    sources: Annotated[
        list[str] | None,
        typer.Argument(help="Files, folders, or URLs to ingest before solving."),
    ] = None,
    demo: bool = typer.Option(False, "--demo", help="Use the packaged Acme Payments demo."),
    project: str | None = typer.Option(None, help="Hidden project name under ~/.tortus/projects."),
    refresh: bool = typer.Option(False, "--refresh", help="Refetch URL sources."),
    max_hops: int = typer.Option(3, help="Traversal hop budget."),
    local_only: bool = typer.Option(False, "--local-only", help="Disable portal hops."),
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write a Markdown solve report to this path."),
    ] = None,
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Continue with deterministic local fallback without prompting.",
    ),
) -> None:
    """Ingest, index, query, and return an evidence-backed action plan."""
    run_solve_flow(
        query_text,
        sources or [],
        demo=demo,
        project=project,
        refresh=refresh,
        max_hops=max_hops,
        local_only=local_only,
        output=output,
        yes=yes,
    )


@app.command()
def demo(
    query_text: str = typer.Option(DEFAULT_DEMO_QUERY, "--query", help="Demo question to ask."),
    project: str = typer.Option("acme-demo", help="Hidden project name for the demo."),
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write a Markdown demo report to this path."),
    ] = None,
    yes: bool = typer.Option(True, "--yes/--prompt", help="Run without fallback prompts."),
) -> None:
    """Run the packaged Acme Payments demo from any directory."""
    run_solve_flow(
        query_text,
        [],
        demo=True,
        project=project,
        refresh=False,
        max_hops=3,
        local_only=False,
        output=output,
        yes=yes,
    )


def run_solve_flow(
    query_text: str,
    sources: list[str],
    *,
    demo: bool,
    project: str | None,
    refresh: bool,
    max_hops: int,
    local_only: bool,
    output: Path | None,
    yes: bool,
) -> None:
    """Run the complete simple solve workflow."""
    if not demo and not sources:
        console.print(
            Panel(
                "Provide at least one source to solve against.\n\n"
                "[bold]Quick start:[/bold]\n"
                "  [bold cyan]tortus demo[/bold cyan]"
                "                                  try the packaged Acme Payments example\n"
                "  [bold cyan]tortus solve \"your question\" ./docs[/bold cyan]"
                "         use your own files or folders\n"
                "  [bold cyan]tortus solve \"your question\" https://...[/bold cyan]"
                "      mix files and URLs",
                title="[bold red]No sources provided[/bold red]",
                border_style="red",
                padding=(1, 2),
            )
        )
        raise typer.Exit(code=1)
    active_project = project or default_solve_project(query_text, sources, demo=demo)
    corpus = DEFAULT_DEMO_CORPUS if demo else "workspace"
    settings = settings_for_solve_project(active_project, corpus)
    fallback_warnings, settings = warn_or_confirm_local_quality(
        settings,
        project=active_project,
        corpus=corpus,
        yes=yes,
    )
    settings.tortus_data_dir.mkdir(parents=True, exist_ok=True)
    settings.tortus_cache_dir.mkdir(parents=True, exist_ok=True)

    print_summary_panel(
        "Tortus Solve",
        [
            (
                "Project",
                f"[bold]{escape(active_project)}[/bold] "
                "[dim](re-runs with the same source reuse this project\'s cached index)[/dim]",
            ),
            ("Data", styled_path(settings.tortus_data_dir)),
            ("Corpus", f"[bold]{escape(corpus)}[/bold]"),
            ("Mode", "demo" if demo else "workspace"),
        ],
        style="cyan",
    )

    if demo:
        with console.status("[bold cyan]Preparing packaged demo corpus...[/bold cyan]"):
            documents, chunks = ingest_builtin(settings, corpus=DEFAULT_DEMO_CORPUS)
        print_summary_panel(
            "Demo Corpus Ready",
            [("Documents", str(documents)), ("Chunks", str(chunks))],
            style="green",
        )
    else:
        with console.status("[bold cyan]Snapshotting sources...[/bold cyan]"):
            ingest_result = ingest_sources(settings, sources, refresh=refresh)
        print_summary_panel(
            "Sources Loaded",
            [
                ("Documents", str(ingest_result.documents)),
                ("Chunks", str(ingest_result.chunks)),
                ("Snapshot", styled_path(ingest_result.out_dir)),
            ],
            style="green",
        )
        print_source_health_result(ingest_result.source_health)

    with console.status("[bold cyan]Building topology-aware retrieval index...[/bold cyan]"):
        stats = build_index(settings, corpus=corpus)
    print_summary_panel(
        "Index Ready",
        [
            ("Nodes", str(stats["nodes"])),
            ("Edges", str(stats["edges"])),
            ("Portal edges", str(stats["portal_edges"])),
        ],
        style="green",
    )

    with console.status("[bold cyan]Retrieving evidence and producing action plan...[/bold cyan]"):
        engine = load_engine(settings)
        result = engine.answer(
            query_text,
            TraversalPolicy(max_hops=max_hops, local_only=local_only, explain_hops=True),
        )
        engine.graph.close()

    # Print quality notice prominently BEFORE the diagnosis so users understand
    # the quality context before reading the results.
    print_quality_notice(result.quality_mode, fallback_warnings)
    print_action_plan(result)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(solve_result_markdown(query_text, result), encoding="utf-8")
        print_summary_panel("Report Written", [("Path", styled_path(output))], style="green")
    print_source_health_result(result.source_health)
    if result.evidence:
        evidence_table = Table(
            title="Citations",
            box=box.SIMPLE_HEAVY,
            header_style="bold cyan",
            expand=True,
        )
        evidence_table.add_column("source", no_wrap=True)
        evidence_table.add_column("range", justify="right", no_wrap=True)
        evidence_table.add_column("text", overflow="fold")
        for span in result.citations[:8]:
            evidence_table.add_row(
                escape(compact_identifier(span.uri, 42)),
                f"{span.start}-{span.end}",
                escape(truncate_text(span.text, 140)),
            )
        console.print(evidence_table)
    # The local-mode fallback warning is already shown above via print_quality_notice.
    non_fallback = [w for w in result.warnings if w not in set(fallback_warnings)]
    print_warnings(non_fallback)
    write_last_project(project=active_project, data_dir=settings.tortus_data_dir, corpus=corpus)
    print_next_steps(
        "[bold]tortus open --last[/bold] to inspect this result in the dashboard",
        "[bold]tortus serve --last --port 8010[/bold] to run the API/dashboard for this project",
    )


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
    last: bool = typer.Option(False, "--last", help="Serve the last tortus solve project."),
    corpus: str | None = typer.Option(None, help="Corpus name to serve."),
    data_dir: Annotated[
        Path | None,
        typer.Option(help="Override TORTUS_DATA_DIR for this command."),
    ] = None,
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate app creation without binding."),
) -> None:
    """Serve the GraphQL API and dashboard."""
    settings = (
        last_project_settings()
        if last
        else settings_with_overrides(get_settings(), corpus=corpus, data_dir=data_dir)
    )
    create_app, uvicorn_runtime = load_api_runtime()
    fastapi_app = create_app(settings)
    if dry_run:
        print_summary_panel(
            "Server Dry Run Passed",
            [
                ("Routes", f"[bold green]{len(fastapi_app.routes)}[/bold green]"),
                ("Corpus", f"[bold]{escape(settings.tortus_corpus)}[/bold]"),
                ("Data", styled_path(settings.tortus_data_dir)),
            ],
            style="green",
        )
        return
    print_summary_panel(
        "Starting Tortus Server",
        [
            ("API", f"[cyan]http://{escape(host)}:{port}/graphql[/cyan]"),
            ("Dashboard", f"[cyan]http://{escape(host)}:{port}/[/cyan]"),
            ("Data", styled_path(settings.tortus_data_dir)),
        ],
        style="cyan",
    )
    uvicorn_runtime.run(fastapi_app, host=host, port=port)


@app.command(name="open")
def open_command(
    host: str = typer.Option("127.0.0.1", help="Host to bind."),
    port: int = typer.Option(8000, help="Port to bind."),
    last: bool = typer.Option(False, "--last", help="Open the last tortus solve project."),
) -> None:
    """Open the dashboard and serve the active or last project."""
    settings = last_project_settings() if last else get_settings()
    create_app, uvicorn_runtime = load_api_runtime()
    url = f"http://{host}:{port}/"
    print_summary_panel(
        "Opening Tortus Dashboard",
        [
            ("Dashboard", f"[cyan]{escape(url)}[/cyan]"),
            ("Corpus", f"[bold]{escape(settings.tortus_corpus)}[/bold]"),
            ("Data", styled_path(settings.tortus_data_dir)),
        ],
        style="cyan",
    )
    webbrowser.open(url)
    console.print(
        f"[dim]Server running at [cyan]{escape(url)}[/cyan] - "
        "press [bold]Ctrl-C[/bold] to stop.[/dim]"
    )
    uvicorn_runtime.run(create_app(settings), host=host, port=port)


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
