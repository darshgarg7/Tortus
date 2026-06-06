"""Pinned public corpus manifest verification helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .corpus import PUBLIC_ENGINEERING_CORPUS
from .ingest import DEFAULT_USER_AGENT, html_to_text, normalize_text, sha256_bytes, sha256_text


@dataclass(frozen=True)
class CorpusFetchResult:
    """Result of fetching or verifying a pinned public corpus manifest."""

    out_path: Path
    sources: int
    fetched: int
    warnings: list[str]


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
) -> CorpusFetchResult:
    """Verify packaged summaries or fetch live source snapshots into the cache."""
    manifest = load_public_manifest()
    out_dir = settings.tortus_cache_dir / "corpora" / manifest["name"]
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    records: list[dict[str, Any]] = []
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
            if cache_path.exists() and not refresh:
                raw = cache_path.read_bytes()
            else:
                try:
                    raw = fetch_public_source(url)
                    cache_path.write_bytes(raw)
                    fetched += 1
                except Exception as exc:
                    warnings.append(f"{url}: {exc}")
                    raw = b""
            if raw:
                extraction_warnings: list[str] = []
                text = html_to_text(
                    raw.decode("utf-8", errors="replace"),
                    warnings=extraction_warnings,
                )
                record["raw_sha256"] = sha256_bytes(raw)
                record["normalized_sha256"] = sha256_text(normalize_text(text))
                record["snapshot_path"] = str(cache_path)
                record["extraction_warnings"] = extraction_warnings
        records.append(record)

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "fetch_enabled": fetch,
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
    )


def fetch_public_source(url: str) -> bytes:
    """Fetch one public corpus source with bounded network behavior."""
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(20.0, connect=5.0),
        headers={"user-agent": DEFAULT_USER_AGENT},
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content
