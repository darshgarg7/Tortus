from tortus.config import Settings
from tortus.eval import run_smoke_eval
from tortus.pipeline import build_index, load_engine
from tortus.report import failure_taxonomy, generate_markdown_report, strategy_summaries


def test_markdown_report_contains_strategy_summary_and_taxonomy(tmp_path) -> None:
    settings = Settings(TORTUS_DATA_DIR=tmp_path / "data", TORTUS_CACHE_DIR=tmp_path / "cache")
    build_index(settings)
    report = run_smoke_eval(load_engine(settings), strategies=("tortus_torus", "bm25"))

    markdown = generate_markdown_report(report)
    summaries = strategy_summaries(report)
    taxonomy = failure_taxonomy(report)

    assert "## Strategy Summary" in markdown
    assert "## Thesis Check" in markdown
    assert "## Suite Breakdown" in markdown
    assert "## Failure Taxonomy" in markdown
    assert "## Cost And Fanout Notes" in markdown
    assert "tortus_torus" in markdown
    assert "bm25" in markdown
    assert summaries
    assert isinstance(taxonomy.total(), int)
