from fastapi.testclient import TestClient

from tortus.api import create_app
from tortus.config import Settings


def test_dashboard_assets_include_diagnostic_fields(tmp_path) -> None:
    settings = Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        TORTUS_CORPUS="engineering",
    )
    with TestClient(create_app(settings)) as client:
        html = client.get("/").text
        script = client.get("/static/app.js")

    assert "Score" in html
    assert "Terms" in html
    assert "Reason" in html
    assert "Rejected candidates" in html
    assert "Unsupported claims" in html
    assert script.status_code == 200
    assert "matched_terms" in script.text
    assert "pruned_candidates" in script.text
