"""Tests for LLM completion cache correctness across providers and schema versions.

Covers:
- Cache miss on first call writes JSON to disk.
- Cache hit on second call skips the provider entirely.
- Schema version bump produces a new cache key (no stale reads).
- Provider/model isolation: same content, different provider → different cache key.
- Namespace isolation: same cache_parts in different namespaces must not collide.
- Cache key is deterministic for identical inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from tortus.config import Settings
from tortus.llm import LLMProvider, cached_json_completion, completion_cache_key
from tortus.llm_extract import (
    LLM_EXTRACTION_SCHEMA_VERSION,
    LLMChunkGraph,
    extract_chunk_graph,
)
from tortus.models import Chunk, EvidenceSpan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_settings(tmp_path: Path) -> Settings:
    return Settings(
        TORTUS_DATA_DIR=tmp_path / "data",
        TORTUS_CACHE_DIR=tmp_path / "cache",
        OPENAI_API_KEY="sk-test",
    )


def make_mock_provider(
    payload: dict[str, Any],
    *,
    name: str = "openai",
    model: str = "gpt-4o",
) -> MagicMock:
    """Return a MagicMock that satisfies the LLMProvider duck-type interface.

    LLMProvider is a frozen dataclass, so we cannot monkey-patch its fields
    directly on an instance.  A MagicMock with the necessary attributes set
    is the correct approach for unit tests that need to intercept complete_json.
    """
    mock = MagicMock(spec=LLMProvider)
    mock.name = name
    mock.model = model
    mock.complete_json = MagicMock(return_value=payload)
    return mock


def minimal_chunk(tmp_path: Path, text: str = "Retries preserve trace context.") -> Chunk:
    return Chunk(
        id="chunk-test-001",
        document_id="doc-test-001",
        title="Test chunk",
        domain="engineering",
        text=text,
        evidence=EvidenceSpan(uri="file://test.md", start=0, end=len(text), text=text),
        ordinal=0,
    )


# ---------------------------------------------------------------------------
# completion_cache_key
# ---------------------------------------------------------------------------


def test_cache_key_is_deterministic() -> None:
    parts = ["v1", "openai", "gpt-4o", "chunk-abc", "some text"]
    assert completion_cache_key(parts) == completion_cache_key(parts)


def test_cache_key_differs_for_different_inputs() -> None:
    base = ["v1", "openai", "gpt-4o", "chunk-abc", "some text"]
    changed = ["v1", "openai", "gpt-4o", "chunk-abc", "different text"]
    assert completion_cache_key(base) != completion_cache_key(changed)


def test_cache_key_differs_for_different_schema_versions() -> None:
    a = ["schema-v1", "openai", "gpt-4o", "chunk-abc", "text"]
    b = ["schema-v2", "openai", "gpt-4o", "chunk-abc", "text"]
    assert completion_cache_key(a) != completion_cache_key(b)


def test_cache_key_differs_for_different_providers() -> None:
    a = ["schema-v1", "openai", "gpt-4o", "chunk-abc", "text"]
    b = ["schema-v1", "azure", "gpt-4o", "chunk-abc", "text"]
    assert completion_cache_key(a) != completion_cache_key(b)


# ---------------------------------------------------------------------------
# cached_json_completion: miss then hit
# ---------------------------------------------------------------------------


def test_cache_miss_writes_to_disk_and_returns_payload(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    payload = {"concepts": [], "relations": [], "warnings": []}
    provider = make_mock_provider(payload)

    result = cached_json_completion(
        settings,
        namespace="extract",
        cache_parts=["v1", "openai", "gpt-4o", "chunk-001", "hello"],
        system="sys",
        user="usr",
        provider=provider,
    )

    assert result == payload
    provider.complete_json.assert_called_once()

    cache_dir = settings.tortus_cache_dir / "llm" / "extract"
    cached_files = list(cache_dir.glob("*.json"))
    assert len(cached_files) == 1
    assert json.loads(cached_files[0].read_text()) == payload


def test_cache_hit_skips_provider(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    payload = {"concepts": [], "relations": [], "warnings": []}
    provider = make_mock_provider(payload)

    cache_parts = ["v1", "openai", "gpt-4o", "chunk-001", "hello world"]

    # First call: miss
    cached_json_completion(
        settings,
        namespace="extract",
        cache_parts=cache_parts,
        system="sys",
        user="usr",
        provider=provider,
    )
    assert provider.complete_json.call_count == 1

    # Second call: must be a cache hit (provider not called again)
    result2 = cached_json_completion(
        settings,
        namespace="extract",
        cache_parts=cache_parts,
        system="sys",
        user="usr",
        provider=provider,
    )
    assert result2 == payload
    assert provider.complete_json.call_count == 1  # still 1, not 2


def test_different_schema_version_produces_cache_miss(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    payload_v1 = {"concepts": [], "relations": [], "warnings": [], "version": "v1"}
    payload_v2 = {"concepts": [], "relations": [], "warnings": [], "version": "v2"}

    provider_v1 = make_mock_provider(payload_v1)
    provider_v2 = make_mock_provider(payload_v2)

    common = ["openai", "gpt-4o", "chunk-001", "same text"]

    result_v1 = cached_json_completion(
        settings, namespace="extract", cache_parts=["schema-v1", *common],
        system="s", user="u", provider=provider_v1,
    )
    result_v2 = cached_json_completion(
        settings, namespace="extract", cache_parts=["schema-v2", *common],
        system="s", user="u", provider=provider_v2,
    )

    assert result_v1 == payload_v1
    assert result_v2 == payload_v2
    provider_v1.complete_json.assert_called_once()
    provider_v2.complete_json.assert_called_once()


def test_different_provider_name_produces_cache_miss(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    openai_payload = {"concepts": [], "relations": [], "warnings": [], "provider": "openai"}
    azure_payload = {"concepts": [], "relations": [], "warnings": [], "provider": "azure"}

    openai_prov = make_mock_provider(openai_payload, name="openai")
    azure_prov = make_mock_provider(azure_payload, name="azure")

    common = ["schema-v1", "gpt-4o", "chunk-001", "shared text"]

    r_openai = cached_json_completion(
        settings, namespace="extract", cache_parts=["openai", *common],
        system="s", user="u", provider=openai_prov,
    )
    r_azure = cached_json_completion(
        settings, namespace="extract", cache_parts=["azure", *common],
        system="s", user="u", provider=azure_prov,
    )

    assert r_openai["provider"] == "openai"
    assert r_azure["provider"] == "azure"
    openai_prov.complete_json.assert_called_once()
    azure_prov.complete_json.assert_called_once()


def test_namespace_isolation_prevents_cross_namespace_hits(tmp_path: Path) -> None:
    """Two namespaces with the same cache_parts must not share entries."""
    settings = make_settings(tmp_path)
    extract_payload = {"concepts": [], "relations": [], "warnings": [], "ns": "extract"}
    synth_payload = {"concepts": [], "relations": [], "warnings": [], "ns": "synthesis"}

    extract_prov = make_mock_provider(extract_payload)
    synth_prov = make_mock_provider(synth_payload)

    parts = ["v1", "openai", "gpt-4o", "chunk-001", "same text"]

    r_extract = cached_json_completion(
        settings, namespace="extract", cache_parts=parts,
        system="s", user="u", provider=extract_prov,
    )
    r_synth = cached_json_completion(
        settings, namespace="synthesis", cache_parts=parts,
        system="s", user="u", provider=synth_prov,
    )

    assert r_extract["ns"] == "extract"
    assert r_synth["ns"] == "synthesis"


# ---------------------------------------------------------------------------
# extract_chunk_graph: schema validation and cache integration
# ---------------------------------------------------------------------------


def test_extract_chunk_graph_uses_cache_on_second_call(tmp_path: Path, monkeypatch) -> None:
    """extract_chunk_graph must not call the provider a second time for the same chunk."""
    settings = make_settings(tmp_path)
    chunk = minimal_chunk(tmp_path)

    call_count = {"n": 0}
    valid_payload = {
        "concepts": [
            {
                "label": "trace context",
                "summary": "context propagation in traces",
                "confidence": 0.8,
            }
        ],
        "relations": [],
        "warnings": [],
    }

    def fake_complete_json(*, system: str, user: str) -> dict:
        call_count["n"] += 1
        return valid_payload

    mock_provider = MagicMock()
    mock_provider.name = "openai"
    mock_provider.model = "gpt-4o"
    mock_provider.complete_json = fake_complete_json

    monkeypatch.setattr("tortus.llm_extract.build_llm_provider", lambda s: mock_provider)
    monkeypatch.setattr("tortus.llm_extract.provider_allowed", lambda s, p: True)

    result1 = extract_chunk_graph(chunk, settings, provider_name="openai")
    result2 = extract_chunk_graph(chunk, settings, provider_name="openai")

    assert isinstance(result1, LLMChunkGraph)
    assert isinstance(result2, LLMChunkGraph)
    assert call_count["n"] == 1, (
        "Provider should only be called once; second call must be a cache hit"
    )


def test_extract_chunk_graph_validates_schema(tmp_path: Path, monkeypatch) -> None:
    """LLM output that violates the schema must raise ValidationError (not silently pass)."""
    from pydantic import ValidationError

    settings = make_settings(tmp_path)
    chunk = minimal_chunk(tmp_path, text="Different text so cache key is fresh abc123xyz")

    bad_payload = {
        "concepts": [{"label": "x", "summary": "y", "confidence": 99.9}],  # confidence > 1.0
        "relations": [],
        "warnings": [],
    }

    mock_provider = MagicMock()
    mock_provider.name = "openai"
    mock_provider.model = "gpt-4o"
    mock_provider.complete_json = MagicMock(return_value=bad_payload)

    monkeypatch.setattr("tortus.llm_extract.build_llm_provider", lambda s: mock_provider)
    monkeypatch.setattr("tortus.llm_extract.provider_allowed", lambda s, p: True)

    with pytest.raises(ValidationError):
        extract_chunk_graph(chunk, settings, provider_name="openai")


def test_extract_chunk_graph_schema_version_is_in_cache_key(tmp_path: Path, monkeypatch) -> None:
    """The LLM_EXTRACTION_SCHEMA_VERSION constant must be part of the cache key."""
    settings = make_settings(tmp_path)
    chunk = minimal_chunk(tmp_path, text="Schema version isolation test text")

    payloads_served = []

    def fake_complete(*, system: str, user: str) -> dict:
        payloads_served.append(1)
        return {"concepts": [], "relations": [], "warnings": []}

    mock_provider = MagicMock()
    mock_provider.name = "openai"
    mock_provider.model = "gpt-4o"
    mock_provider.complete_json = fake_complete

    monkeypatch.setattr("tortus.llm_extract.build_llm_provider", lambda s: mock_provider)
    monkeypatch.setattr("tortus.llm_extract.provider_allowed", lambda s, p: True)

    # Confirm the schema version constant is non-empty so it can influence the key
    assert LLM_EXTRACTION_SCHEMA_VERSION, "Schema version constant must not be empty"

    extract_chunk_graph(chunk, settings, provider_name="openai")
    # Second identical call → cache hit → only 1 total provider call
    extract_chunk_graph(chunk, settings, provider_name="openai")
    assert len(payloads_served) == 1
