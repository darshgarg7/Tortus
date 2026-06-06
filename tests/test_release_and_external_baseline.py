from tortus.baselines import run_strategy
from tortus.config import Settings
from tortus.models import TraversalPolicy
from tortus.pipeline import build_index, load_engine
from tortus.release import run_doctor


def test_doctor_sees_packaged_dashboard_assets(tmp_path) -> None:
    settings = Settings(TORTUS_DATA_DIR=tmp_path / "data", TORTUS_CACHE_DIR=tmp_path / "cache")
    checks = {check.name: check for check in run_doctor(settings)}
    assert checks["template asset"].ok
    assert checks["static asset"].ok
    assert checks["typed marker"].ok
    assert checks["data path"].ok


def test_graphrag_external_baseline_skips_cleanly(tmp_path) -> None:
    settings = Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        TORTUS_CORPUS="engineering",
    )
    build_index(settings)
    run = run_strategy(
        load_engine(settings),
        "How did token migration connect authentication and tracing?",
        "graphrag_external",
        TraversalPolicy(),
    )
    assert run.external
    assert run.skipped
    assert run.strategy == "graphrag_external"
    assert run.warnings
