"""Markdown benchmark reporting and failure taxonomy."""

from collections import Counter, defaultdict
from collections.abc import Sequence
from math import ceil, floor

from pydantic import BaseModel

from .eval import EvalReport, EvalRow


class StrategySummary(BaseModel):
    """Represent StrategySummary data."""

    strategy: str
    pass_rate: float
    term_recall: float
    source_recall: float
    path_recall: float
    p50_latency_ms: float
    p95_latency_ms: float
    mean_nodes_visited: float
    mean_portal_hops: float
    mean_shard_fanout: float
    mean_shard_crossings: float
    warning_rate: float


def strategy_summaries(report: EvalReport) -> list[StrategySummary]:
    """Summarize strategy summaries."""
    grouped: defaultdict[str, list[EvalRow]] = defaultdict(list)
    for row in report.rows:
        grouped[row.strategy].append(row)

    summaries: list[StrategySummary] = []
    for strategy in sorted(grouped):
        rows = grouped[strategy]
        summaries.append(
            StrategySummary(
                strategy=strategy,
                pass_rate=average([1.0 if row.passed else 0.0 for row in rows]),
                term_recall=average([row.term_recall for row in rows]),
                source_recall=average([row.source_recall for row in rows]),
                path_recall=average([row.path_recall for row in rows]),
                p50_latency_ms=percentile([row.latency_ms for row in rows], 0.50),
                p95_latency_ms=percentile([row.latency_ms for row in rows], 0.95),
                mean_nodes_visited=average([float(row.nodes_visited) for row in rows]),
                mean_portal_hops=average([float(row.portal_hops) for row in rows]),
                mean_shard_fanout=average([float(row.shard_fanout) for row in rows]),
                mean_shard_crossings=average([float(row.shard_crossings) for row in rows]),
                warning_rate=average([1.0 if row.warnings else 0.0 for row in rows]),
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
    """Generate generate markdown report."""
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
            "and path recall >= 0.50. This is a local v0 benchmark, not a "
            "production superiority claim."
        ),
        "",
        "## Strategy Summary",
        "",
        markdown_table(
            [
                "strategy",
                "pass",
                "term",
                "source",
                "path",
                "p50 ms",
                "p95 ms",
                "nodes",
                "portals",
                "fanout",
                "cross",
                "warn",
            ],
            [
                [
                    summary.strategy,
                    f"{summary.pass_rate:.2f}",
                    f"{summary.term_recall:.2f}",
                    f"{summary.source_recall:.2f}",
                    f"{summary.path_recall:.2f}",
                    f"{summary.p50_latency_ms:.1f}",
                    f"{summary.p95_latency_ms:.1f}",
                    f"{summary.mean_nodes_visited:.1f}",
                    f"{summary.mean_portal_hops:.1f}",
                    f"{summary.mean_shard_fanout:.1f}",
                    f"{summary.mean_shard_crossings:.1f}",
                    f"{summary.warning_rate:.2f}",
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
        "tortus ingest --corpus engineering",
        "tortus index --layout torus",
        "tortus golden-set --out data/golden_set.json --count 100",
        "tortus eval --suite benchmark --strategies all \\",
        "  --json-out data/eval/benchmark.json \\",
        "  --duckdb-out data/eval/results.duckdb",
        "tortus report --eval-json data/eval/benchmark.json --out data/reports/eval-report.md",
        "```",
        "",
    ]
    return "\n".join(lines)


def classify_row(row: EvalRow) -> list[str]:
    """Classify classify row."""
    labels: list[str] = []
    if row.term_recall <= 0:
        labels.append("missing_expected_terms")
    if row.source_recall <= 0:
        labels.append("missing_expected_sources")
    if row.path_recall <= 0:
        labels.append("missing_expected_path")
    lowered_warnings = " ".join(row.warnings).lower()
    if "budget" in lowered_warnings:
        labels.append("budget_limited")
    if "lexical" in lowered_warnings or "seed" in lowered_warnings:
        labels.append("candidate_generation_miss")
    if row.shard_fanout > 6:
        labels.append("high_shard_fanout")
    return labels


def thesis_check(summaries: list[StrategySummary]) -> str:
    """Summarize thesis check."""
    tortus = next((summary for summary in summaries if summary.strategy == "tortus_torus"), None)
    baselines = [summary for summary in summaries if summary.strategy != "tortus_torus"]
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

    if pass_delta > 0:
        verdict = "v0 supports keeping the toroidal traversal hypothesis alive"
    elif pass_delta == 0:
        verdict = "v0 is inconclusive on pass rate"
    else:
        verdict = "v0 is a negative result for the current toroidal traversal policy"

    return (
        f"{verdict}: `tortus_torus` is {pass_delta:+.2f} pass-rate points, "
        f"{source_delta:+.2f} source-recall points, and {path_delta:+.2f} "
        f"path-recall points versus the strongest current baseline "
        f"(`{best.strategy}`)."
    )


def boundary_crossing_summary(report: EvalReport) -> str:
    """Summarize boundary crossing summary."""
    rows = [row for row in report.rows if row.suite == "boundary_crossing"]
    if not rows:
        return "No boundary-crossing questions were included in this report."
    slice_report = EvalReport(suite="boundary_crossing", rows=rows)
    summaries = strategy_summaries(slice_report)
    return markdown_table(
        ["strategy", "pass", "source", "path", "portals", "fanout", "cross"],
        [
            [
                summary.strategy,
                f"{summary.pass_rate:.2f}",
                f"{summary.source_recall:.2f}",
                f"{summary.path_recall:.2f}",
                f"{summary.mean_portal_hops:.1f}",
                f"{summary.mean_shard_fanout:.1f}",
                f"{summary.mean_shard_crossings:.1f}",
            ]
            for summary in summaries
        ],
    )


def suite_breakdown_summary(report: EvalReport) -> str:
    """Summarize suite breakdown summary."""
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
                    f"{summary.p95_latency_ms:.1f}",
                ]
            )
    return markdown_table(["suite", "strategy", "pass", "source", "path", "p95 ms"], rows)


def taxonomy_summary(taxonomy: Counter[str]) -> str:
    """Summarize taxonomy summary."""
    if not taxonomy:
        return "No failures or warnings were recorded."
    return markdown_table(
        ["category", "count"],
        [[category, str(count)] for category, count in taxonomy.most_common()],
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
        f"({warning_heaviest.warning_rate:.2f})."
    )


def hardest_misses_summary(rows: list[EvalRow], limit: int = 8) -> str:
    """Summarize hardest misses summary."""
    if not rows:
        return "No failing eval rows were recorded."
    return markdown_table(
        ["question", "strategy", "term", "source", "path", "warnings"],
        [
            [
                row.question_id,
                row.strategy,
                f"{row.term_recall:.2f}",
                f"{row.source_recall:.2f}",
                f"{row.path_recall:.2f}",
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
    """Clean clean cell."""
    return value.replace("|", "\\|").replace("\n", " ")


def average(values: Sequence[float]) -> float:
    """Return average."""
    return sum(values) / len(values) if values else 0.0


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
