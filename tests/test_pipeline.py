from tortus.config import Settings
from tortus.eval import questions_for_suite, run_eval, run_smoke_eval
from tortus.models import TraversalPolicy
from tortus.pipeline import build_index, ingest_builtin, load_engine


def test_ingest_index_query_eval_roundtrip(tmp_path) -> None:
    settings = Settings(TORTUS_DATA_DIR=tmp_path / "data", TORTUS_CACHE_DIR=tmp_path / "cache")
    documents, chunks = ingest_builtin(settings)
    assert documents >= 4
    assert chunks >= 4

    stats = build_index(settings)
    assert stats["nodes"] >= 4
    assert stats["edges"] >= 1

    engine = load_engine(settings)
    result = engine.answer("How did token migration connect authentication and tracing?")
    assert result.evidence
    assert result.budget.nodes_visited > 0
    assert result.budget.shard_fanout > 0

    report = run_smoke_eval(engine)
    assert report.rows
    assert report.pass_rate("tortus_torus") > 0
    assert {row.strategy for row in report.rows} >= {"tortus_torus", "vector_only", "bm25"}

    full_report = run_eval(engine, suite="full", strategies=("tortus_torus", "vector_only"))
    assert len(questions_for_suite("full")) > len(questions_for_suite("smoke"))
    assert len(full_report.rows) == len(questions_for_suite("full")) * 2
    assert any(row.path_recall > 0 for row in full_report.rows)

    constrained = engine.answer(
        "How did token migration connect authentication and tracing?",
        TraversalPolicy(max_portal_hops=0),
    )
    assert constrained.budget.portal_hops == 0
    assert "portal-hop budget" in " ".join(constrained.warnings)
