from tortus.audit import AuditRecord, export_audit_suite, import_audit_records
from tortus.config import Settings
from tortus.corpus_manifest import fetch_or_verify_public_corpus, load_public_manifest


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
