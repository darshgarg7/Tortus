from tortus.config import Settings
from tortus.ingest import (
    WorkspaceIngestResult,
    ingest_workspace,
    load_snapshot_documents,
    pdf_to_text,
)
from tortus.pipeline import build_index, load_engine


def test_workspace_ingests_local_markdown_html_and_text(tmp_path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# Runbook\nToken retries preserve traces.", encoding="utf-8")
    (docs / "page.html").write_text(
        "<html><body><h1>Gateway</h1><p>Audience validation failed.</p></body></html>",
        encoding="utf-8",
    )
    (docs / "note.txt").write_text("OpenTelemetry context propagation matters.", encoding="utf-8")
    (docs / "spreadsheet.xlsx").write_bytes(b"not supported yet")

    settings = Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        TORTUS_CORPUS="workspace",
    )
    result = ingest_workspace(settings, [str(docs)], refresh=False)

    assert isinstance(result, WorkspaceIngestResult)
    assert result.documents == 3
    assert result.chunks >= 3
    assert result.source_health.unsupported_sources == 1
    assert "Unsupported source skipped" in " ".join(result.source_health.warnings)
    assert result.manifest_path.exists()
    documents = load_snapshot_documents(result.out_dir)
    assert {document.metadata["source_type"] for document in documents} == {"file"}
    assert all(document.metadata["raw_sha256"] for document in documents)

    stats = build_index(settings)
    assert stats["nodes"] >= 3
    answer = load_engine(settings).answer("How do token retries relate to traces?")
    assert answer.evidence


def test_url_ingestion_uses_pinned_snapshot_without_refetch(tmp_path, monkeypatch) -> None:
    calls = {"count": 0}

    def fake_fetch(url: str) -> tuple[bytes, dict[str, str]]:
        calls["count"] += 1
        return (
            (
                b"<html><body><h1>Incident</h1>"
                b"<p>Gateway retries dropped trace context.</p></body></html>"
            ),
            {"content-type": "text/html", "etag": "abc", "last-modified": "today"},
        )

    monkeypatch.setattr("tortus.ingest.fetch_url", fake_fetch)
    settings = Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        TORTUS_CORPUS="workspace",
    )

    first = ingest_workspace(settings, ["https://example.com/incident"], refresh=False)
    second = ingest_workspace(settings, ["https://example.com/incident"], refresh=False)

    assert first.documents == 1
    assert second.documents == 1
    assert calls["count"] == 1
    document = load_snapshot_documents(second.out_dir)[0]
    assert document.metadata["etag"] == "abc"
    assert document.metadata["last_modified"] == "today"


def test_manifest_and_pdf_warning_path(tmp_path) -> None:
    manifest = tmp_path / "sources.toml"
    note = tmp_path / "note.txt"
    note.write_text("Trace context survives retries.", encoding="utf-8")
    manifest.write_text(f'sources = ["{note}"]\n', encoding="utf-8")
    settings = Settings(TORTUS_DATA_DIR=tmp_path / "data", TORTUS_CACHE_DIR=tmp_path / "cache")

    result = ingest_workspace(settings, [], manifest=manifest, refresh=False)
    assert result.documents == 1

    warnings: list[str] = []
    assert pdf_to_text(b"not a real pdf", warnings=warnings) == ""
    assert warnings
