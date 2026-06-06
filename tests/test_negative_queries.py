from tortus.config import Settings
from tortus.pipeline import build_index, load_engine


def test_unanswerable_query_withholds_answer(tmp_path) -> None:
    settings = Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        TORTUS_CORPUS="engineering",
    )
    build_index(settings)
    engine = load_engine(settings)

    result = engine.answer("What is tomorrow's weather forecast for Chicago?")

    assert result.confidence == 0
    assert result.evidence == []
    assert "not find enough source-backed evidence" in result.answer
    assert "intentionally withheld" in " ".join(result.warnings)
