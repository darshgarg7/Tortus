import json
from pathlib import Path

from tortus.config import Settings
from tortus.eval import run_eval
from tortus.pipeline import build_index, load_engine
from tortus.report import strategy_summaries


def test_smoke_benchmark_stays_within_snapshot_thresholds(tmp_path) -> None:
    snapshot = json.loads(Path("data/benchmark_snapshots/smoke_thresholds.json").read_text())
    settings = Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        TORTUS_CORPUS=snapshot["corpus"],
    )
    build_index(settings)
    report = run_eval(
        load_engine(settings),
        suite=snapshot["suite"],
        strategies=tuple(snapshot["strategies"]),
    )
    summaries = {summary.strategy: summary for summary in strategy_summaries(report)}

    for strategy, thresholds in snapshot["strategies"].items():
        summary = summaries[strategy]
        if "min_pass_rate" in thresholds:
            assert summary.pass_rate >= thresholds["min_pass_rate"]
        if "min_faithfulness" in thresholds:
            assert summary.faithfulness >= thresholds["min_faithfulness"]
        if "min_source_recall" in thresholds:
            assert summary.source_recall >= thresholds["min_source_recall"]
        if "max_mean_portal_hops" in thresholds:
            assert summary.mean_portal_hops <= thresholds["max_mean_portal_hops"]
