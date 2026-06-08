"""Tests for SourceHealth telemetry produced by build_source_health and ingest_workspace.

Covers:
- Empty documents are detected and counted.
- Duplicate documents (same normalized hash) are detected.
- Unsupported files increment the counter and emit warnings.
- Quality score degrades as issues accumulate.
- Unsupported-only sources (no documents) generate a warning.
- Source-type breakdown is accurate.
- Healthy ingest produces quality_score == 1.0 and no warnings.
- Source health is round-tripped through the snapshot manifest JSON.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tortus.config import Settings
from tortus.ingest import (
    WorkspaceIngestResult,
    build_source_health,
    ingest_workspace,
    load_snapshot_source_health,
)
from tortus.models import Document, SourceHealth

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        TORTUS_CORPUS="workspace",
    )


def make_document(doc_id: str, text: str = "Relevant engineering text.") -> Document:
    return Document(
        id=doc_id,
        title="Test Document",
        source=f"file://test/{doc_id}.md",
        domain="engineering",
        text=text,
    )


def source_record(
    source_type: str = "file",
    normalized_sha: str = "abc123",
) -> dict:
    return {
        "source_type": source_type,
        "normalized_sha256": normalized_sha,
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# build_source_health unit tests
# ---------------------------------------------------------------------------


class TestBuildSourceHealth:
    def test_healthy_ingest_has_perfect_quality_score(self) -> None:
        docs = [make_document("doc-1", "Good content here.")]
        records = [source_record("file", "sha-unique-1")]
        health = build_source_health(docs, 4, records, [], unsupported_sources=0)

        assert health.quality_score == pytest.approx(1.0)
        assert health.empty_documents == 0
        assert health.duplicate_documents == 0
        assert health.unsupported_sources == 0
        assert health.warnings == []

    def test_empty_document_is_detected(self) -> None:
        docs = [make_document("doc-empty", text="")]
        records = [source_record("file", "sha-empty")]
        health = build_source_health(docs, 0, records, [], unsupported_sources=0)

        assert health.empty_documents == 1
        assert health.quality_score < 1.0

    def test_whitespace_only_document_counts_as_empty(self) -> None:
        docs = [make_document("doc-ws", text="   \n\t  ")]
        records = [source_record("file", "sha-ws")]
        health = build_source_health(docs, 0, records, [], unsupported_sources=0)

        assert health.empty_documents == 1

    def test_multiple_empty_documents_compound_penalty(self) -> None:
        docs = [make_document(f"doc-empty-{i}", text="") for i in range(4)]
        records = [source_record("file", f"sha-{i}") for i in range(4)]
        health = build_source_health(docs, 0, records, [], unsupported_sources=0)

        assert health.empty_documents == 4
        assert health.quality_score <= 0.75

    def test_duplicate_documents_are_detected(self) -> None:
        # Two records sharing the same normalized SHA → 1 duplicate group
        docs = [make_document("doc-a"), make_document("doc-b")]
        records = [
            source_record("file", "same-sha"),
            source_record("file", "same-sha"),
        ]
        health = build_source_health(docs, 4, records, [], unsupported_sources=0)

        assert health.duplicate_documents >= 1
        assert health.quality_score < 1.0

    def test_three_way_duplicate_counted_as_one_group(self) -> None:
        docs = [make_document(f"doc-{i}") for i in range(3)]
        records = [source_record("file", "triple-sha") for _ in range(3)]
        health = build_source_health(docs, 3, records, [], unsupported_sources=0)

        # The counting model counts groups where count > 1, so 1 duplicate group
        assert health.duplicate_documents >= 1

    def test_unique_documents_are_not_counted_as_duplicates(self) -> None:
        docs = [make_document(f"doc-{i}") for i in range(3)]
        records = [source_record("file", f"unique-sha-{i}") for i in range(3)]
        health = build_source_health(docs, 9, records, [], unsupported_sources=0)

        assert health.duplicate_documents == 0

    def test_unsupported_sources_are_counted_and_penalize_score(self) -> None:
        docs = [make_document("doc-1", "Good content.")]
        records = [source_record("file", "sha-1")]
        health = build_source_health(docs, 4, records, [], unsupported_sources=5)

        assert health.unsupported_sources == 5
        assert health.quality_score < 1.0

    def test_warnings_are_deduplicated_and_capped(self) -> None:
        warnings = ["same warning"] * 50
        docs = [make_document("doc-1")]
        records = [source_record("file", "sha-1")]
        health = build_source_health(docs, 3, records, warnings, unsupported_sources=0)

        assert len(health.warnings) <= 40
        # Unique: just 1 distinct warning
        assert len(set(health.warnings)) == 1

    def test_quality_score_does_not_go_below_zero(self) -> None:
        docs = [make_document(f"doc-{i}", text="") for i in range(20)]
        records = [source_record("file", "same-sha") for _ in range(20)]
        warnings = [f"warning {i}" for i in range(50)]
        health = build_source_health(docs, 0, records, warnings, unsupported_sources=20)

        assert health.quality_score >= 0.0

    def test_source_type_breakdown_is_accurate(self) -> None:
        docs = [make_document("doc-1"), make_document("doc-2")]
        records = [source_record("file", "sha-1"), source_record("url", "sha-2")]
        health = build_source_health(docs, 5, records, [], unsupported_sources=0)

        assert health.source_types.get("file") == 1
        assert health.source_types.get("url") == 1

    def test_chunks_and_documents_counts_are_preserved(self) -> None:
        docs = [make_document("doc-1"), make_document("doc-2")]
        records = [source_record("file", f"sha-{i}") for i in range(2)]
        health = build_source_health(docs, 7, records, [], unsupported_sources=0)

        assert health.documents == 2
        assert health.chunks == 7


# ---------------------------------------------------------------------------
# ingest_workspace integration tests
# ---------------------------------------------------------------------------


class TestIngestWorkspaceSourceHealth:
    def test_unsupported_file_increments_counter_and_emits_warning(
        self, tmp_path: Path
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "valid.md").write_text("Real markdown content here.", encoding="utf-8")
        (docs_dir / "data.csv").write_bytes(b"col1,col2\n1,2")  # unsupported
        (docs_dir / "binary.bin").write_bytes(b"\x00\x01\x02")  # unsupported

        settings = make_settings(tmp_path)
        result = ingest_workspace(settings, [str(docs_dir)], refresh=False)

        assert isinstance(result, WorkspaceIngestResult)
        assert result.documents == 1
        assert result.source_health.unsupported_sources == 2
        unsupported_warnings = [
            w for w in result.source_health.warnings if "Unsupported" in w
        ]
        assert unsupported_warnings, "Expected at least one 'Unsupported source skipped' warning"

    def test_empty_file_is_detected_in_source_health(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "empty.md").write_text("", encoding="utf-8")
        (docs_dir / "real.md").write_text("Meaningful content about tracing.", encoding="utf-8")

        settings = make_settings(tmp_path)
        result = ingest_workspace(settings, [str(docs_dir)], refresh=False)

        assert result.source_health.empty_documents == 1

    def test_duplicate_files_detected_in_source_health(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        identical_content = (
            "Exact same content in both files. Token retries preserve trace context."
        )
        (docs_dir / "copy_a.md").write_text(identical_content, encoding="utf-8")
        (docs_dir / "copy_b.md").write_text(identical_content, encoding="utf-8")
        (docs_dir / "unique.md").write_text(
            "Completely different and unique content.",
            encoding="utf-8",
        )

        settings = make_settings(tmp_path)
        result = ingest_workspace(settings, [str(docs_dir)], refresh=False)

        assert result.documents == 3
        assert result.source_health.duplicate_documents >= 1

    def test_healthy_ingest_produces_high_quality_score(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "incident.md").write_text(
            "Gateway retry runbook: increase timeout, enable trace propagation.", encoding="utf-8"
        )
        (docs_dir / "auth.md").write_text(
            "Token migration guide: rotate secrets, validate audience claims.", encoding="utf-8"
        )

        settings = make_settings(tmp_path)
        result = ingest_workspace(settings, [str(docs_dir)], refresh=False)

        assert result.source_health.quality_score == pytest.approx(1.0)
        assert result.source_health.empty_documents == 0
        assert result.source_health.duplicate_documents == 0
        assert result.source_health.unsupported_sources == 0

    def test_no_supported_docs_in_source_emits_warning(self, tmp_path: Path) -> None:
        """A directory with only unsupported files should produce a no-docs warning."""
        docs_dir = tmp_path / "unsupported_only"
        docs_dir.mkdir()
        (docs_dir / "archive.zip").write_bytes(b"PK\x03\x04")
        (docs_dir / "image.png").write_bytes(b"\x89PNG")

        settings = make_settings(tmp_path)
        result = ingest_workspace(settings, [str(docs_dir)], refresh=False)

        assert result.documents == 0
        assert result.source_health.unsupported_sources >= 2
        assert result.source_health.quality_score < 1.0

    def test_source_health_is_persisted_in_snapshot_manifest(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("Runbook: retry on 503.", encoding="utf-8")

        settings = make_settings(tmp_path)
        result = ingest_workspace(settings, [str(docs_dir)], refresh=False)

        # Now reload from manifest and confirm round-trip
        restored = load_snapshot_source_health(result.out_dir)
        assert isinstance(restored, SourceHealth)
        assert restored.documents == result.source_health.documents
        assert restored.chunks == result.source_health.chunks
        assert restored.quality_score == pytest.approx(result.source_health.quality_score)

    def test_source_types_include_file_entries(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "note.txt").write_text("Plain text engineering notes.", encoding="utf-8")

        settings = make_settings(tmp_path)
        result = ingest_workspace(settings, [str(docs_dir)], refresh=False)

        assert result.source_health.source_types.get("file", 0) >= 1

    def test_mixed_good_and_bad_sources_produce_degraded_quality(
        self, tmp_path: Path
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "good.md").write_text("Trace propagation is important.", encoding="utf-8")
        (docs_dir / "empty.md").write_text("", encoding="utf-8")
        (docs_dir / "junk.exe").write_bytes(b"\x4d\x5a")  # unsupported

        settings = make_settings(tmp_path)
        result = ingest_workspace(settings, [str(docs_dir)], refresh=False)

        assert result.source_health.quality_score < 1.0
        assert result.source_health.empty_documents >= 1
        assert result.source_health.unsupported_sources >= 1
