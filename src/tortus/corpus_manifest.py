"""Pinned public corpus manifest verification helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import Settings
from .corpus import PUBLIC_ENGINEERING_CORPUS, chunk_corpus, write_snapshot
from .ingest import (
    DEFAULT_USER_AGENT,
    extract_url_text,
    normalize_text,
    sha256_bytes,
    sha256_text,
)
from .models import Document


@dataclass(frozen=True)
class CorpusFetchResult:
    """Result of fetching or verifying a pinned public corpus manifest."""

    out_path: Path
    sources: int
    fetched: int
    warnings: list[str]
    corpus_path: Path | None = None
    documents: int = 0
    chunks: int = 0


def load_public_manifest() -> dict[str, Any]:
    """Load the packaged public engineering corpus manifest."""
    path = resources.files("tortus.resources").joinpath("public_corpus_manifest.json")
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def fetch_or_verify_public_corpus(
    settings: Settings,
    *,
    fetch: bool = False,
    refresh: bool = False,
    materialize: bool = False,
    corpus_name: str = "external-engineering",
) -> CorpusFetchResult:
    """Verify packaged summaries or fetch live source snapshots into an indexable corpus."""
    manifest = load_public_manifest()
    out_dir = settings.tortus_cache_dir / "corpora" / manifest["name"]
    raw_dir = out_dir / "raw"
    text_dir = out_dir / "normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
    documents: list[Document] = []
    fetched = 0

    built_in_by_url = {
        str(document.metadata.get("url", "")): document for document in PUBLIC_ENGINEERING_CORPUS
    }
    for source in manifest["sources"]:
        record = dict(source)
        url = str(source["url"])
        built_in = built_in_by_url.get(url)
        if built_in is not None:
            record["summary_normalized_sha256"] = sha256_text(normalize_text(built_in.text))
            record["summary_source"] = built_in.source

        if fetch:
            cache_path = raw_dir / f"{source['id']}.raw"
            headers_path = raw_dir / f"{source['id']}.headers.json"
            if cache_path.exists() and not refresh:
                raw = cache_path.read_bytes()
                headers = read_cached_headers(headers_path)
            else:
                try:
                    raw, headers = fetch_public_source(url)
                    cache_path.write_bytes(raw)
                    headers_path.write_text(
                        json.dumps(headers, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    fetched += 1
                except Exception as exc:
                    warnings.append(f"{url}: {exc}")
                    raw = b""
                    headers = {}
            if raw:
                extraction_warnings: list[str] = []
                content_type = headers.get("content-type", "text/html")
                text = extract_url_text(
                    url,
                    raw,
                    content_type=content_type,
                    warnings=extraction_warnings,
                )
                normalized = normalize_text(text)
                raw_sha = sha256_bytes(raw)
                normalized_sha = sha256_text(normalized)
                normalized_path = text_dir / f"{source['id']}.txt"
                normalized_path.write_text(normalized + "\n", encoding="utf-8")
                record.update(
                    {
                        "source_name": str(source.get("source_name", "")),
                        "content_type": content_type,
                        "raw_sha256": raw_sha,
                        "normalized_sha256": normalized_sha,
                        "snapshot_path": str(cache_path),
                        "headers_path": str(headers_path),
                        "normalized_path": str(normalized_path),
                        "retrieved_at": datetime.now(tz=UTC).isoformat(),
                        "etag": headers.get("etag", ""),
                        "last_modified": headers.get("last-modified", ""),
                        "extraction_warnings": extraction_warnings,
                    }
                )
                expected_raw = str(source.get("expected_raw_sha256", ""))
                expected_normalized = str(source.get("expected_normalized_sha256", ""))
                if expected_raw and expected_raw != raw_sha:
                    warnings.append(f"{source['id']}: raw SHA256 changed from manifest pin")
                if expected_normalized and expected_normalized != normalized_sha:
                    warnings.append(
                        f"{source['id']}: normalized SHA256 changed from manifest pin"
                    )
                if extraction_warnings:
                    warnings.extend(f"{source['id']}: {warning}" for warning in extraction_warnings)
                if materialize and normalized:
                    documents.append(document_from_snapshot(source, normalized, record))
        records.append(record)

    corpus_path: Path | None = None
    chunks_count = 0
    if materialize and documents:
        corpus_path = settings.tortus_data_dir / "corpus" / corpus_name
        chunks = chunk_corpus(documents)
        write_snapshot(documents, chunks, corpus_path)
        chunks_count = len(chunks)
        (corpus_path / "snapshot_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "generated_at": datetime.now(tz=UTC).isoformat(),
                    "corpus": corpus_name,
                    "source_manifest": manifest["name"],
                    "source_manifest_snapshot": manifest.get("snapshot", ""),
                    "source_manifest_snapshot_date": manifest.get("snapshot_date", ""),
                    "cache_manifest": str(out_dir / "manifest.json"),
                    "documents": len(documents),
                    "chunks": chunks_count,
                    "sources": records,
                    "warnings": warnings,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "source_manifest": manifest["name"],
        "source_manifest_snapshot": manifest.get("snapshot", ""),
        "source_manifest_snapshot_date": manifest.get("snapshot_date", ""),
        "fetch_enabled": fetch,
        "materialized_corpus": corpus_name if materialize and documents else "",
        "sources": records,
        "warnings": warnings,
    }
    out_path = out_dir / "manifest.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return CorpusFetchResult(
        out_path=out_path,
        sources=len(records),
        fetched=fetched,
        warnings=warnings,
        corpus_path=corpus_path,
        documents=len(documents),
        chunks=chunks_count,
    )


def fetch_public_source(url: str) -> tuple[bytes, dict[str, str]]:
    """Fetch one public corpus source with bounded network behavior."""
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(20.0, connect=5.0),
        headers={"user-agent": DEFAULT_USER_AGENT},
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content, {key.lower(): value for key, value in response.headers.items()}


def read_cached_headers(path: Path) -> dict[str, str]:
    """Read cached response headers for a public corpus source."""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key).lower(): str(value) for key, value in payload.items()}


def document_from_snapshot(
    source: dict[str, Any],
    normalized: str,
    record: dict[str, Any],
) -> Document:
    """Create a Tortus document from a fetched external source snapshot."""
    parsed = urlparse(str(source["url"]))
    source_id = str(source["id"])
    return Document(
        id=f"doc:external:{source_id}:{record['normalized_sha256'][:12]}",
        title=str(source.get("title", source_id)),
        source=str(source["url"]),
        domain=parsed.netloc or str(source.get("source_name", "external")),
        text=normalized,
        metadata={
            "source_type": "external_url",
            "source_manifest_id": source_id,
            "source_manifest_name": str(source.get("source_name", "")),
            "url": str(source["url"]),
            "license_note": str(source.get("license_note", "")),
            "content_type": str(record.get("content_type", "")),
            "raw_sha256": str(record.get("raw_sha256", "")),
            "normalized_sha256": str(record.get("normalized_sha256", "")),
            "snapshot_path": str(record.get("snapshot_path", "")),
            "headers_path": str(record.get("headers_path", "")),
            "normalized_path": str(record.get("normalized_path", "")),
            "retrieved_at": str(record.get("retrieved_at", "")),
            "etag": str(record.get("etag", "")),
            "last_modified": str(record.get("last_modified", "")),
            "warnings": list(record.get("extraction_warnings", [])),
        },
    )
