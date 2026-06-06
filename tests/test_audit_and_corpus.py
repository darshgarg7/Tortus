from tortus.audit import AuditRecord, export_audit_suite, import_audit_records
from tortus.config import Settings
from tortus.corpus_manifest import fetch_or_verify_public_corpus, load_public_manifest
from tortus.eval import apply_audit_file, questions_for_suite
from tortus.ingest import load_snapshot_documents


def test_audit_export_import_roundtrip(tmp_path) -> None:
    out = tmp_path / "audit.jsonl"
    count = export_audit_suite("smoke", out)
    assert count > 0
    first = AuditRecord.model_validate_json(out.read_text(encoding="utf-8").splitlines()[0])
    reviewed = first.model_copy(update={"status": "approved", "auditor": "human"})
    reviewed_path = tmp_path / "reviewed.jsonl"
    reviewed_path.write_text(reviewed.model_dump_json() + "\n", encoding="utf-8")

    imported = tmp_path / "imported.jsonl"
    assert import_audit_records(reviewed_path, out=imported) == 1
    assert "approved" in imported.read_text(encoding="utf-8")


def test_public_corpus_manifest_verifies_without_live_fetch(tmp_path) -> None:
    manifest = load_public_manifest()
    assert manifest["name"] == "public-engineering"
    settings = Settings(TORTUS_DATA_DIR=tmp_path / "data", TORTUS_CACHE_DIR=tmp_path / "cache")
    result = fetch_or_verify_public_corpus(settings, fetch=False)
    assert result.sources >= 5
    assert result.fetched == 0
    assert result.out_path.exists()


def test_public_corpus_fetch_materializes_indexable_snapshot(tmp_path, monkeypatch) -> None:
    def fake_fetch(url: str) -> tuple[bytes, dict[str, str]]:
        return (
            (
                b"<html><body><h1>Trace Context</h1>"
                b"<p>Traceparent carries distributed trace identity across services.</p>"
                b"</body></html>"
            ),
            {"content-type": "text/html", "etag": "demo"},
        )

    monkeypatch.setattr("tortus.corpus_manifest.fetch_public_source", fake_fetch)
    settings = Settings(TORTUS_DATA_DIR=tmp_path / "data", TORTUS_CACHE_DIR=tmp_path / "cache")

    result = fetch_or_verify_public_corpus(
        settings,
        fetch=True,
        materialize=True,
        corpus_name="external-demo",
    )

    assert result.fetched == result.sources
    assert result.documents == result.sources
    assert result.chunks >= result.documents
    assert result.corpus_path is not None
    documents = load_snapshot_documents(result.corpus_path)
    assert {document.metadata["source_type"] for document in documents} == {"external_url"}
    assert documents[0].metadata["etag"] == "demo"


def test_human_audit_file_overrides_eval_labels(tmp_path) -> None:
    question = questions_for_suite("smoke")[0]
    audit_record = AuditRecord(
        id=question.id,
        suite=question.suite,
        question=question.question,
        expected_terms=["reviewed-term"],
        expected_evidence_uris=["reviewed://source"],
        expected_path_labels=["portal"],
        status="approved",
        auditor="Darsh",
        reviewed_at="2026-06-06T00:00:00Z",
    )
    audit_file = tmp_path / "audit.jsonl"
    audit_file.write_text(audit_record.model_dump_json() + "\n", encoding="utf-8")

    audited = apply_audit_file((question,), audit_file)[0]

    assert audited.audit_status == "human_reviewed"
    assert audited.expected_terms == ("reviewed-term",)
    assert audited.expected_sources == ("reviewed://source",)
    assert audited.expected_edge_types == ("portal",)
