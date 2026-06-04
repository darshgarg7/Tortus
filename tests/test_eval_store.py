import duckdb

from tortus.config import Settings
from tortus.eval import run_smoke_eval
from tortus.eval_store import write_eval_duckdb, write_eval_json
from tortus.pipeline import build_index, load_engine


def test_eval_report_writes_json_and_duckdb(tmp_path) -> None:
    settings = Settings(TORTUS_DATA_DIR=tmp_path / "data", TORTUS_CACHE_DIR=tmp_path / "cache")
    build_index(settings)
    report = run_smoke_eval(load_engine(settings), strategies=("tortus_torus", "bm25"))

    json_path = tmp_path / "eval" / "smoke.json"
    duckdb_path = tmp_path / "eval" / "results.duckdb"
    write_eval_json(report, json_path)
    run_id = write_eval_duckdb(report, duckdb_path)

    assert json_path.exists()
    assert run_id
    with duckdb.connect(str(duckdb_path)) as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM eval_rows").fetchone()[0]
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info('eval_rows')").fetchall()
        }
    assert row_count == len(report.rows)
    assert "path_recall" in columns
