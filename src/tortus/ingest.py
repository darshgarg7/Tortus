"""Workspace document ingestion and pinned snapshot helpers."""

from __future__ import annotations

import hashlib
import html.parser
import importlib
import json
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

import httpx

from .config import Settings
from .corpus import chunk_corpus, write_snapshot
from .models import Document

SUPPORTED_EXTENSIONS = {".md", ".mdx", ".txt", ".html", ".htm", ".pdf"}
DEFAULT_USER_AGENT = "tortus-rag/0.1 (+https://github.com/darshgarg7/Tortus)"
MAX_URL_BYTES = 5_000_000


@dataclass(frozen=True)
class IngestedSource:
    """A normalized source document plus extraction metadata."""

    document: Document
    raw_bytes: bytes
    metadata: dict[str, Any]


@dataclass(frozen=True)
class WorkspaceIngestResult:
    """Summary of a workspace ingestion run."""

    documents: int
    chunks: int
    out_dir: Path
    manifest_path: Path
    warnings: list[str]


class TextHTMLParser(html.parser.HTMLParser):
    """Small stdlib fallback for extracting readable text from HTML."""

    def __init__(self) -> None:
        """Initialize the fallback parser."""
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track tags that should not contribute visible text."""
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        """Leave skipped blocks when their end tag is seen."""
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        """Collect visible text."""
        if not self.skip_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        """Return collapsed extracted text."""
        return normalize_text(" ".join(self.parts))


def ingest_workspace(
    settings: Settings,
    sources: list[str],
    *,
    manifest: Path | None = None,
    refresh: bool = False,
) -> WorkspaceIngestResult:
    """Ingest local files, directories, and URLs into a pinned workspace snapshot."""
    resolved_sources = list(sources)
    if manifest is not None:
        resolved_sources.extend(read_manifest_sources(manifest))
    if not resolved_sources:
        raise ValueError(
            "workspace ingestion requires at least one file, directory, URL, or manifest"
        )

    out_dir = settings.tortus_data_dir / "corpus" / "workspace"
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    documents: list[Document] = []
    source_records: list[dict[str, Any]] = []
    for source in resolved_sources:
        for ingested in ingest_one_source(source, raw_dir=raw_dir, refresh=refresh):
            documents.append(ingested.document)
            source_records.append(ingested.metadata)
            warnings.extend(str(item) for item in ingested.metadata.get("warnings", []))

    chunks = chunk_corpus(documents)
    write_snapshot(documents, chunks, out_dir)
    manifest_payload = {
        "schema_version": 1,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "corpus": "workspace",
        "documents": len(documents),
        "chunks": len(chunks),
        "sources": source_records,
    }
    manifest_path = out_dir / "snapshot_manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, indent=2) + "\n", encoding="utf-8")
    return WorkspaceIngestResult(
        documents=len(documents),
        chunks=len(chunks),
        out_dir=out_dir,
        manifest_path=manifest_path,
        warnings=warnings,
    )


def ingest_one_source(source: str, *, raw_dir: Path, refresh: bool) -> list[IngestedSource]:
    """Ingest one source string into one or more normalized documents."""
    if is_url(source):
        return [ingest_url(source, raw_dir=raw_dir, refresh=refresh)]
    path = Path(source).expanduser()
    if path.is_dir():
        return [
            ingest_local_file(file_path, raw_dir=raw_dir)
            for file_path in sorted(iter_supported_files(path))
        ]
    if path.is_file():
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return []
        return [ingest_local_file(path, raw_dir=raw_dir)]
    raise ValueError(f"source does not exist or is not supported: {source}")


def iter_supported_files(root: Path) -> Iterable[Path]:
    """Yield supported files recursively beneath a directory."""
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def ingest_local_file(path: Path, *, raw_dir: Path) -> IngestedSource:
    """Ingest one local file into a source-backed Tortus document."""
    raw_bytes = path.read_bytes()
    warnings: list[str] = []
    text = extract_text_for_suffix(path.suffix.lower(), raw_bytes, warnings=warnings)
    normalized = normalize_text(text)
    raw_sha = sha256_bytes(raw_bytes)
    normalized_sha = sha256_text(normalized)
    raw_snapshot = raw_dir / f"{raw_sha}{path.suffix.lower() or '.txt'}"
    if not raw_snapshot.exists():
        raw_snapshot.write_bytes(raw_bytes)
    metadata = {
        "source_type": "file",
        "source": str(path),
        "path": str(path.resolve()),
        "content_type": content_type_for_suffix(path.suffix.lower()),
        "raw_sha256": raw_sha,
        "normalized_sha256": normalized_sha,
        "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat(),
        "snapshot_path": str(raw_snapshot),
        "warnings": warnings,
    }
    return IngestedSource(
        document=Document(
            id=document_id_for_source(str(path.resolve()), normalized_sha),
            title=title_for_text(normalized, fallback=path.stem),
            source=f"file://{path.resolve()}",
            domain=domain_for_path(path),
            text=normalized,
            metadata=metadata,
        ),
        raw_bytes=raw_bytes,
        metadata=metadata,
    )


def ingest_url(source: str, *, raw_dir: Path, refresh: bool) -> IngestedSource:
    """Fetch and ingest one URL with a pinned local raw snapshot."""
    cache_key = sha256_text(source)
    cache_path = raw_dir / f"url-{cache_key}.raw"
    metadata_path = raw_dir / f"url-{cache_key}.metadata.json"
    headers: dict[str, str] = {}
    retrieved_at = datetime.now(tz=UTC).isoformat()
    if cache_path.exists() and not refresh:
        raw_bytes = cache_path.read_bytes()
        cached_metadata = read_url_cache_metadata(metadata_path)
        headers = cached_metadata.get("headers", {})
        retrieved_at = cached_metadata.get("retrieved_at", retrieved_at)
    else:
        raw_bytes, headers = fetch_url(source)
        cache_path.write_bytes(raw_bytes)
        write_url_cache_metadata(
            metadata_path,
            source=source,
            retrieved_at=retrieved_at,
            headers=headers,
        )

    warnings: list[str] = []
    content_type = headers.get("content-type", "text/html")
    text = extract_url_text(source, raw_bytes, content_type=content_type, warnings=warnings)
    normalized = normalize_text(text)
    raw_sha = sha256_bytes(raw_bytes)
    normalized_sha = sha256_text(normalized)
    parsed = urlparse(source)
    metadata = {
        "source_type": "url",
        "source": source,
        "url": source,
        "content_type": content_type,
        "raw_sha256": raw_sha,
        "normalized_sha256": normalized_sha,
        "retrieved_at": retrieved_at,
        "etag": headers.get("etag", ""),
        "last_modified": headers.get("last-modified", ""),
        "snapshot_path": str(cache_path),
        "snapshot_metadata_path": str(metadata_path),
        "warnings": warnings,
    }
    return IngestedSource(
        document=Document(
            id=document_id_for_source(source, normalized_sha),
            title=title_for_text(normalized, fallback=parsed.netloc or source),
            source=source,
            domain=parsed.netloc or "url",
            text=normalized,
            metadata=metadata,
        ),
        raw_bytes=raw_bytes,
        metadata=metadata,
    )


def read_url_cache_metadata(path: Path) -> dict[str, Any]:
    """Read URL snapshot metadata sidecar if it exists."""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    headers = payload.get("headers", {})
    return {
        "retrieved_at": str(payload.get("retrieved_at", "")),
        "headers": {str(key).lower(): str(value) for key, value in headers.items()}
        if isinstance(headers, dict)
        else {},
    }


def write_url_cache_metadata(
    path: Path,
    *,
    source: str,
    retrieved_at: str,
    headers: dict[str, str],
) -> None:
    """Write URL snapshot metadata that is preserved across no-refresh ingests."""
    payload = {
        "schema_version": 1,
        "source": source,
        "retrieved_at": retrieved_at,
        "headers": headers,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def fetch_url(source: str) -> tuple[bytes, dict[str, str]]:
    """Fetch a URL using bounded timeouts and a Tortus user-agent."""
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={"user-agent": DEFAULT_USER_AGENT},
    ) as client:
        response = client.get(source)
        response.raise_for_status()
        content = response.content
    if len(content) > MAX_URL_BYTES:
        raise ValueError(f"url response exceeds {MAX_URL_BYTES} bytes: {source}")
    headers = {key.lower(): value for key, value in response.headers.items()}
    return content, headers


def extract_text_for_suffix(suffix: str, raw_bytes: bytes, *, warnings: list[str]) -> str:
    """Extract normalized text for a supported local file suffix."""
    if suffix in {".md", ".mdx"}:
        return markdown_to_text(raw_bytes.decode("utf-8", errors="replace"))
    if suffix == ".txt":
        return raw_bytes.decode("utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        return html_to_text(raw_bytes.decode("utf-8", errors="replace"), warnings=warnings)
    if suffix == ".pdf":
        return pdf_to_text(raw_bytes, warnings=warnings)
    return ""


def extract_url_text(
    source: str,
    raw_bytes: bytes,
    *,
    content_type: str,
    warnings: list[str],
) -> str:
    """Extract text from a URL response using content-type hints."""
    if "pdf" in content_type.lower() or source.lower().endswith(".pdf"):
        return pdf_to_text(raw_bytes, warnings=warnings)
    return html_to_text(raw_bytes.decode("utf-8", errors="replace"), warnings=warnings)


def markdown_to_text(text: str) -> str:
    """Reduce Markdown into readable text while keeping headings and prose."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text


def html_to_text(text: str, *, warnings: list[str]) -> str:
    """Extract useful text from HTML with optional libraries and stdlib fallback."""
    try:
        trafilatura = importlib.import_module("trafilatura")

        extracted = cast(str | None, trafilatura.extract(text))
        if extracted:
            return extracted
    except Exception as exc:  # pragma: no cover - optional parser behavior
        warnings.append(f"trafilatura extraction failed: {exc}")

    try:
        bs4 = importlib.import_module("bs4")
        beautiful_soup = bs4.BeautifulSoup

        soup = beautiful_soup(text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        return cast(str, soup.get_text(" "))
    except Exception as exc:  # pragma: no cover - optional parser behavior
        warnings.append(f"beautifulsoup extraction failed: {exc}")

    parser = TextHTMLParser()
    parser.feed(text)
    return parser.text()


def pdf_to_text(raw_bytes: bytes, *, warnings: list[str]) -> str:
    """Extract text from a PDF, warning clearly when extraction is unavailable or empty."""
    try:
        pypdf = importlib.import_module("pypdf")
        pdf_reader = pypdf.PdfReader
    except ImportError:
        warnings.append("PDF extraction requires installing tortus-rag[ingest].")
        return ""

    try:
        from io import BytesIO

        reader = pdf_reader(BytesIO(raw_bytes))
        parts = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        warnings.append(f"PDF extraction failed: {exc}")
        return ""
    text = "\n".join(part for part in parts if part.strip())
    if not text.strip():
        warnings.append("PDF contained no extractable text; it may be scanned or image-only.")
    return text


def read_manifest_sources(path: Path) -> list[str]:
    """Read file and URL sources from a TOML manifest."""
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    raw_sources = payload.get("sources", [])
    sources: list[str] = []
    if isinstance(raw_sources, list):
        for item in raw_sources:
            if isinstance(item, str):
                sources.append(item)
            elif isinstance(item, dict):
                value = item.get("url") or item.get("path") or item.get("source")
                if value:
                    sources.append(str(value))
    elif isinstance(raw_sources, dict):
        for key in ("paths", "urls"):
            values = raw_sources.get(key, [])
            if isinstance(values, list):
                sources.extend(str(value) for value in values)
    return sources


def load_snapshot_documents(corpus_dir: Path) -> list[Document]:
    """Load persisted documents from a Tortus corpus snapshot."""
    path = corpus_dir / "documents.json"
    if not path.exists():
        raise FileNotFoundError(f"workspace corpus snapshot not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Document.model_validate(item) for item in payload]


def is_url(value: str) -> bool:
    """Return whether a source string looks like an HTTP URL."""
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_text(text: str) -> str:
    """Collapse whitespace and normalize source text for deterministic snapshots."""
    return " ".join(text.replace("\x00", " ").split())


def sha256_bytes(value: bytes) -> str:
    """Return a SHA256 hex digest for bytes."""
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    """Return a SHA256 hex digest for text."""
    return sha256_bytes(value.encode("utf-8"))


def document_id_for_source(source: str, normalized_sha: str) -> str:
    """Return a deterministic document id for an ingested source."""
    slug = re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")[-64:] or "source"
    return f"doc:workspace:{slug}:{normalized_sha[:12]}"


def title_for_text(text: str, *, fallback: str) -> str:
    """Infer a concise title from the first useful line or sentence."""
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        stripped = part.strip()
        if stripped:
            return stripped[:96]
    return fallback


def domain_for_path(path: Path) -> str:
    """Return a stable local domain label for a file path."""
    parent = path.parent.name
    return parent if parent and parent != "." else "workspace"


def content_type_for_suffix(suffix: str) -> str:
    """Return a content type label for a file suffix."""
    return {
        ".md": "text/markdown",
        ".mdx": "text/markdown",
        ".txt": "text/plain",
        ".html": "text/html",
        ".htm": "text/html",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")
