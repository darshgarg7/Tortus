"""Markdown benchmark reporting and failure taxonomy."""

from collections import Counter, defaultdict
from collections.abc import Sequence
from math import ceil, floor

from pydantic import BaseModel

from .eval import EvalReport, EvalRow


class StrategySummary(BaseModel):
    """Aggregate metrics for one retrieval strategy."""

    strategy: str
    rows: int
    pass_rate: float
    pass_ci_low: float
    pass_ci_high: float
    term_recall: float
    source_recall: float
    path_recall: float
    path_precision: float
    faithfulness: float
    p50_latency_ms: float
    p95_latency_ms: float
    mean_nodes_visited: float
    mean_portal_hops: float
    mean_shard_fanout: float
    mean_shard_crossings: float
    warning_rate: float
    skipped_rate: float
    external_rate: float


def strategy_summaries(report: EvalReport) -> list[StrategySummary]:
    """Summarize strategy summaries."""
    grouped: defaultdict[str, list[EvalRow]] = defaultdict(list)
    for row in report.rows:
        grouped[row.strategy].append(row)

    summaries: list[StrategySummary] = []
    for strategy in sorted(grouped):
        rows = grouped[strategy]
        pass_values = [1.0 if row.passed else 0.0 for row in rows]
        pass_rate = average(pass_values)
        ci_low, ci_high = proportion_interval(pass_rate, len(rows))
        summaries.append(
            StrategySummary(
                strategy=strategy,
                rows=len(rows),
                pass_rate=pass_rate,
                pass_ci_low=ci_low,
                pass_ci_high=ci_high,
                term_recall=average([row.term_recall for row in rows]),
                source_recall=average([row.source_recall for row in rows]),
                path_recall=average([row.path_recall for row in rows]),
                path_precision=average([row.path_precision for row in rows]),
                faithfulness=average([row.faithfulness for row in rows]),
                p50_latency_ms=percentile([row.latency_ms for row in rows], 0.50),
                p95_latency_ms=percentile([row.latency_ms for row in rows], 0.95),
                mean_nodes_visited=average([float(row.nodes_visited) for row in rows]),
                mean_portal_hops=average([float(row.portal_hops) for row in rows]),
                mean_shard_fanout=average([float(row.shard_fanout) for row in rows]),
                mean_shard_crossings=average([float(row.shard_crossings) for row in rows]),
                warning_rate=average([1.0 if row.warnings else 0.0 for row in rows]),
                skipped_rate=average([1.0 if row.skipped else 0.0 for row in rows]),
                external_rate=average([1.0 if row.external else 0.0 for row in rows]),
            )
        )
    return summaries


def failure_taxonomy(report: EvalReport) -> Counter[str]:
    """Summarize failure taxonomy."""
    counts: Counter[str] = Counter()
    for row in report.rows:
        if row.passed and not row.warnings:
            continue
        labels = classify_row(row)
        if not labels and row.warnings:
            labels = ["warning_only"]
        for label in labels:
            counts[label] += 1
    return counts


def generate_markdown_report(report: EvalReport) -> str:
    """Generate a markdown benchmark report."""
    summaries = strategy_summaries(report)
    taxonomy = failure_taxonomy(report)
    failed_rows = sorted(
        [row for row in report.rows if not row.passed],
        key=lambda row: (
            row.term_recall + row.source_recall + row.path_recall,
            row.strategy,
            row.question_id,
        ),
    )

    lines: list[str] = [
        "# Tortus Evaluation Report",
        "",
        (
            f"Suite: `{report.suite}`. Rows: `{len(report.rows)}`. "
            "A pass requires term recall >= 0.50, source recall >= 0.50, "
            "path recall >= 0.50, and faithfulness >= 0.50 for answerable questions. "
            "Negative questions pass only when unsupported answers are withheld. "
            "Skipped external adapters are reported separately and are not counted as wins. "
            "This is a local v2 benchmark, not a production superiority claim."
        ),
        "",
        "## Strategy Summary",
        "",
        markdown_table(
            [
                "strategy",
                "rows",
                "pass",
                "95% CI",
                "term",
                "source",
                "path",
                "precision",
                "faith",
                "p50 ms",
                "p95 ms",
                "nodes",
                "portals",
                "fanout",
                "cross",
                "warn",
                "skipped",
            ],
            [
                [
                    summary.strategy,
                    str(summary.rows),
                    f"{summary.pass_rate:.2f}",
                    f"{summary.pass_ci_low:.2f}-{summary.pass_ci_high:.2f}",
                    f"{summary.term_recall:.2f}",
                    f"{summary.source_recall:.2f}",
                    f"{summary.path_recall:.2f}",
                    f"{summary.path_precision:.2f}",
                    f"{summary.faithfulness:.2f}",
                    f"{summary.p50_latency_ms:.1f}",
                    f"{summary.p95_latency_ms:.1f}",
                    f"{summary.mean_nodes_visited:.1f}",
                    f"{summary.mean_portal_hops:.1f}",
                    f"{summary.mean_shard_fanout:.1f}",
                    f"{summary.mean_shard_crossings:.1f}",
                    f"{summary.warning_rate:.2f}",
                    f"{summary.skipped_rate:.2f}",
                ]
                for summary in summaries
            ],
        ),
        "",
        "## Thesis Check",
        "",
        thesis_check(summaries),
        "",
        "## Suite Breakdown",
        "",
        suite_breakdown_summary(report),
        "",
        "## Audit Status",
        "",
        audit_status_summary(report),
        "",
        "## External Baselines",
        "",
        external_baseline_summary(report),
        "",
        "## Boundary-Crossing Slice",
        "",
        boundary_crossing_summary(report),
        "",
        "## Failure Taxonomy",
        "",
        taxonomy_summary(taxonomy),
        "",
        "## Cost And Fanout Notes",
        "",
        cost_and_fanout_notes(summaries),
        "",
        "## Hardest Misses",
        "",
        hardest_misses_summary(failed_rows),
        "",
        "## Reproduction",
        "",
        "```bash",
        "tortus ingest --corpus public-engineering --data-dir data",
        "tortus index --layout torus --corpus public-engineering --data-dir data",
        "tortus golden-set --out data/golden_set.json --count 100",
        f"tortus eval --suite benchmark --strategies {reproduction_strategy_arg(report)} \\",
        "  --corpus public-engineering \\",
        "  --data-dir data \\",
        *reproduction_audit_args(report),
        "  --json-out data/eval/benchmark.json \\",
        "  --duckdb-out data/eval/results.duckdb",
        "tortus report --eval-json data/eval/benchmark.json --out data/reports/eval-report.md",
        "```",
        "",
    ]
    return "\n".join(lines)


def reproduction_strategy_arg(report: EvalReport) -> str:
    """Return the strategy selector that matches the report rows."""
    return "all_with_external" if any(row.external for row in report.rows) else "all"


def reproduction_audit_args(report: EvalReport) -> list[str]:
    """Return audit flags when a report used the committed assistant audit file."""
    statuses = {row.audit_status for row in report.rows}
    if "assistant_reviewed" in statuses:
        return ["  --audit-file data/audits/golden100.codex-reviewed.jsonl \\"]
    return []


def classify_row(row: EvalRow) -> list[str]:
    """Classify a failed eval row for the failure taxonomy."""
    labels: list[str] = []
    if row.term_recall <= 0:
        labels.append("missing_expected_terms")
    if row.source_recall <= 0:
        labels.append("missing_expected_sources")
    if row.path_recall <= 0:
        labels.append("missing_expected_path")
    if row.path_precision < 0.5 and row.hops_taken:
        labels.append("low_path_precision")
    if row.faithfulness < 0.5:
        labels.append("low_faithfulness")
    lowered_warnings = " ".join(row.warnings).lower()
    if "budget" in lowered_warnings:
        labels.append("budget_limited")
    if "lexical" in lowered_warnings or "seed" in lowered_warnings:
        labels.append("candidate_generation_miss")
    if row.shard_fanout > 6:
        labels.append("high_shard_fanout")
    return labels


def thesis_check(summaries: list[StrategySummary]) -> str:
    """Compare Tortus against the strongest current baseline."""
    tortus = next((summary for summary in summaries if summary.strategy == "tortus_torus"), None)
    baselines = [
        summary
        for summary in summaries
        if summary.strategy != "tortus_torus" and summary.skipped_rate < 1.0
    ]
    if tortus is None:
        return "No `tortus_torus` row was present, so the thesis cannot be evaluated."
    if not baselines:
        return "`tortus_torus` ran, but no baselines were provided for comparison."

    best = max(
        baselines,
        key=lambda summary: (
            summary.pass_rate,
            summary.source_recall,
            summary.path_recall,
            -summary.p95_latency_ms,
        ),
    )
    pass_delta = tortus.pass_rate - best.pass_rate
    source_delta = tortus.source_recall - best.source_recall
    path_delta = tortus.path_recall - best.path_recall
    faith_delta = tortus.faithfulness - best.faithfulness

    if pass_delta > 0:
        verdict = "v2 supports keeping the toroidal traversal hypothesis alive"
    elif pass_delta == 0:
        verdict = "v2 is inconclusive on pass rate"
    else:
        verdict = "v2 is a negative result for the current toroidal traversal policy"

    return (
        f"{verdict}: `tortus_torus` is {pass_delta:+.2f} pass-rate points, "
        f"{source_delta:+.2f} source-recall points, and {path_delta:+.2f} "
        f"path-recall points, and {faith_delta:+.2f} faithfulness points versus the "
        "strongest current baseline "
        f"(`{best.strategy}`)."
    )


def boundary_crossing_summary(report: EvalReport) -> str:
    """Summarize behavior on boundary-crossing questions."""
    rows = [row for row in report.rows if row.suite == "boundary_crossing"]
    if not rows:
        return "No boundary-crossing questions were included in this report."
    slice_report = EvalReport(suite="boundary_crossing", rows=rows)
    summaries = strategy_summaries(slice_report)
    return markdown_table(
        ["strategy", "pass", "source", "path", "precision", "faith", "portals", "fanout", "cross"],
        [
            [
                summary.strategy,
                f"{summary.pass_rate:.2f}",
                f"{summary.source_recall:.2f}",
                f"{summary.path_recall:.2f}",
                f"{summary.path_precision:.2f}",
                f"{summary.faithfulness:.2f}",
                f"{summary.mean_portal_hops:.1f}",
                f"{summary.mean_shard_fanout:.1f}",
                f"{summary.mean_shard_crossings:.1f}",
            ]
            for summary in summaries
        ],
    )


def suite_breakdown_summary(report: EvalReport) -> str:
    """Summarize strategy performance by suite."""
    suites = sorted({row.suite for row in report.rows})
    if not suites:
        return "No suite rows were recorded."
    rows: list[list[str]] = []
    for suite in suites:
        suite_rows = [row for row in report.rows if row.suite == suite]
        suite_report = EvalReport(suite=suite, rows=suite_rows)
        for summary in strategy_summaries(suite_report):
            rows.append(
                [
                    suite,
                    summary.strategy,
                    f"{summary.pass_rate:.2f}",
                    f"{summary.source_recall:.2f}",
                    f"{summary.path_recall:.2f}",
                    f"{summary.path_precision:.2f}",
                    f"{summary.faithfulness:.2f}",
                    f"{summary.p95_latency_ms:.1f}",
                ]
            )
    return markdown_table(
        ["suite", "strategy", "pass", "source", "path", "precision", "faith", "p95 ms"],
        rows,
    )


def taxonomy_summary(taxonomy: Counter[str]) -> str:
    """Render the failure taxonomy."""
    if not taxonomy:
        return "No failures or warnings were recorded."
    return markdown_table(
        ["category", "count"],
        [[category, str(count)] for category, count in taxonomy.most_common()],
    )


def audit_status_summary(report: EvalReport) -> str:
    """Summarize human audit labels represented in the report."""
    counts = Counter(row.audit_status for row in report.rows)
    return markdown_table(
        ["audit status", "rows"],
        [[status, str(count)] for status, count in counts.most_common()],
    )


def external_baseline_summary(report: EvalReport) -> str:
    """Summarize external baseline availability and skip reasons."""
    external_rows = [row for row in report.rows if row.external]
    if not external_rows:
        return "No external baseline rows were requested."
    skipped = sum(row.skipped for row in external_rows)
    warnings = Counter("; ".join(row.warnings) for row in external_rows if row.warnings)
    warning_text = taxonomy_summary(warnings) if warnings else "No external baseline warnings."
    return (
        f"External rows: `{len(external_rows)}`. Skipped rows: `{skipped}`.\n\n"
        + warning_text
    )


def cost_and_fanout_notes(summaries: list[StrategySummary]) -> str:
    """Summarize cost and fanout notes."""
    if not summaries:
        return "No strategy summaries were available."
    highest_fanout = max(summaries, key=lambda summary: summary.mean_shard_fanout)
    slowest = max(summaries, key=lambda summary: summary.p95_latency_ms)
    warning_heaviest = max(summaries, key=lambda summary: summary.warning_rate)
    return (
        f"Highest mean shard fanout: `{highest_fanout.strategy}` "
        f"({highest_fanout.mean_shard_fanout:.1f}). "
        f"Highest p95 latency: `{slowest.strategy}` ({slowest.p95_latency_ms:.1f} ms). "
        f"Highest warning rate: `{warning_heaviest.strategy}` "
        f"({warning_heaviest.warning_rate:.2f}). "
        "The V2 selectivity target is path recall >= 0.90, path precision >= 0.60, "
        "mean fanout <= 5.5, and mean portal hops <= 5.0."
    )


def hardest_misses_summary(rows: list[EvalRow], limit: int = 8) -> str:
    """Render the lowest-scoring eval rows."""
    if not rows:
        return "No failing eval rows were recorded."
    return markdown_table(
        ["question", "strategy", "term", "source", "path", "precision", "faith", "warnings"],
        [
            [
                row.question_id,
                row.strategy,
                f"{row.term_recall:.2f}",
                f"{row.source_recall:.2f}",
                f"{row.path_recall:.2f}",
                f"{row.path_precision:.2f}",
                f"{row.faithfulness:.2f}",
                "; ".join(row.warnings) if row.warnings else "",
            ]
            for row in rows[:limit]
        ],
    )


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    """Render markdown table."""
    clean_headers = [clean_cell(header) for header in headers]
    lines = [
        "| " + " | ".join(clean_headers) + " |",
        "| " + " | ".join("---" for _ in clean_headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(clean_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def clean_cell(value: str) -> str:
    """Escape markdown table cell text."""
    return value.replace("|", "\\|").replace("\n", " ")


def average(values: Sequence[float]) -> float:
    """Return average."""
    return sum(values) / len(values) if values else 0.0


def proportion_interval(rate: float, count: int) -> tuple[float, float]:
    """Return a compact normal-approximate 95% interval for a pass rate."""
    if count <= 0:
        return (0.0, 0.0)
    margin = 1.96 * ((rate * (1.0 - rate) / count) ** 0.5)
    return (max(0.0, rate - margin), min(1.0, rate + margin))


def percentile(values: Sequence[float], quantile: float) -> float:
    """Return percentile."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * quantile
    lower = floor(rank)
    upper = ceil(rank)
    if lower == upper:
        return ordered[lower]
    lower_weight = upper - rank
    upper_weight = rank - lower
    return ordered[lower] * lower_weight + ordered[upper] * upper_weight
