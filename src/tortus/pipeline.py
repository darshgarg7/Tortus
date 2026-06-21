"""High-level ingest, index, and engine-loading pipeline."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .corpus import chunk_corpus, load_builtin_corpus, write_snapshot
from .embeddings import build_embedding_provider
from .graph_store import GraphStore
from .ingest import WorkspaceIngestResult, ingest_workspace, load_snapshot_documents
from .llm import quality_mode
from .llm_extract import extract_graph_with_settings
from .models import ConceptNode, Document
from .synthesis import build_action_plan_enhancer
from .torus import assign_torus
from .traversal import QueryEngine
from .vector import build_vector_index, load_vector_index, vector_index_path


def data_paths(settings: Settings) -> dict[str, Path]:
    """Return all persisted data paths for the active runtime settings."""
    root = settings.tortus_data_dir
    return {
        "root": root,
        "corpus": root / "corpus" / settings.tortus_corpus,
        "graph": root / "graph.sqlite3",
        "index": vector_index_path(root, settings.tortus_vector_backend),
        "graph_export": root / "graph.json",
        "build_metadata": root / "build_metadata.json",
    }


def ingest_builtin(settings: Settings, corpus: str | None = None) -> tuple[int, int]:
    """Ingest a built-in corpus snapshot into the configured data directory."""
    corpus = corpus or settings.tortus_corpus
    documents = load_builtin_corpus(corpus)
    chunks = chunk_corpus(documents)
    write_snapshot(documents, chunks, data_paths(settings)["root"] / "corpus" / corpus)
    return len(documents), len(chunks)


def ingest_sources(
    settings: Settings,
    sources: list[str],
    *,
    manifest: Path | None = None,
    refresh: bool = False,
) -> WorkspaceIngestResult:
    """Ingest user-provided sources into the workspace corpus."""
    return ingest_workspace(settings, sources, manifest=manifest, refresh=refresh)


def build_index(
    settings: Settings,
    corpus: str | None = None,
    *,
    max_edges_per_phrase: int | None = None,
) -> dict[str, int]:
    """Build the graph store and vector index for the selected corpus."""
    corpus = corpus or settings.tortus_corpus
    documents = load_documents(settings, corpus)
    chunks = chunk_corpus(documents)
    nodes, edges = extract_graph_with_settings(
        chunks,
        settings,
        max_edges_per_phrase=max_edges_per_phrase,
    )
    embeddings = build_embedding_provider(settings)
    node_vectors = embeddings.embed([node.label + "\n" + node.text for node in nodes])
    nodes = assign_torus(nodes, node_vectors)
    paths = data_paths(settings)
    if paths["graph"].exists():
        paths["graph"].unlink()
    graph = GraphStore(paths["graph"])
    graph.upsert_nodes(nodes)
    graph.upsert_edges(edges)
    graph.export_json(paths["graph_export"])
    build_vector_index(settings.tortus_vector_backend, nodes, node_vectors).save(paths["index"])
    stats = graph.stats()
    write_build_metadata(
        paths["build_metadata"],
        build_metadata(
            settings,
            corpus=corpus,
            documents=documents,
            embedding_dimensions=int(node_vectors.shape[1]) if node_vectors.ndim == 2 else 0,
            max_edges_per_phrase=max_edges_per_phrase,
            stats=stats,
        ),
    )
    graph.close()
    return stats


def load_documents(settings: Settings, corpus: str) -> list[Document]:
    """Load documents from a built-in corpus or persisted workspace snapshot."""
    snapshot_dir = data_paths(settings)["root"] / "corpus" / corpus
    if corpus == "workspace" or (snapshot_dir / "documents.json").exists():
        return load_snapshot_documents(snapshot_dir)
    return load_builtin_corpus(corpus)


def load_engine(settings: Settings) -> QueryEngine:
    """Load a query engine, building persisted artifacts if needed."""
    paths = data_paths(settings)
    if index_rebuild_required(settings, paths):
        build_index(settings)
    graph = GraphStore(paths["graph"])
    index = load_vector_index(settings.tortus_vector_backend, paths["index"])
    embeddings = build_embedding_provider(settings)
    return QueryEngine(
        graph=graph,
        index=index,
        embeddings=embeddings,
        action_plan_enhancer=build_action_plan_enhancer(settings),
        quality_mode=quality_mode(settings, "synthesis"),
    )


def load_nodes(settings: Settings) -> list[ConceptNode]:
    """Load all persisted concept nodes for the configured graph."""
    paths = data_paths(settings)
    if index_rebuild_required(settings, paths):
        build_index(settings)
    graph = GraphStore(paths["graph"])
    nodes = graph.list_nodes()
    graph.close()
    return nodes


def index_rebuild_required(settings: Settings, paths: dict[str, Path]) -> bool:
    """Return whether persisted graph/vector artifacts are missing or stale."""
    if not paths["graph"].exists() or not paths["index"].exists():
        return True
    stored = read_build_metadata(paths["build_metadata"])
    if not stored:
        return True
    try:
        documents = load_documents(settings, settings.tortus_corpus)
    except (FileNotFoundError, ValueError, json.JSONDecodeError):
        return True
    expected = build_metadata(settings, corpus=settings.tortus_corpus, documents=documents)
    return metadata_signature(stored) != metadata_signature(expected)


def build_metadata(
    settings: Settings,
    *,
    corpus: str,
    documents: list[Document],
    embedding_dimensions: int | None = None,
    max_edges_per_phrase: int | None = None,
    stats: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return metadata that identifies the inputs used for an index build."""
    metadata: dict[str, Any] = {
        "schema_version": 1,
        "built_at": datetime.now(tz=UTC).isoformat(),
        "corpus": corpus,
        "documents_fingerprint": documents_fingerprint(documents),
        "document_count": len(documents),
        "embedding_provider": settings.tortus_embedding_provider,
        "embedding_model": settings.tortus_embedding_model,
        "embedding_dimensions_requested": settings.tortus_embedding_dimensions,
        "azure_openai_embedding_deployment": settings.azure_openai_embedding_deployment,
        "extraction_provider": settings.tortus_extraction_provider,
        "vector_backend": settings.tortus_vector_backend,
        "max_edges_per_phrase": max_edges_per_phrase,
    }
    if embedding_dimensions is not None:
        metadata["embedding_dimensions"] = embedding_dimensions
    if stats is not None:
        metadata["stats"] = stats
    return metadata


def documents_fingerprint(documents: list[Document]) -> str:
    """Return a stable digest for the document payload being indexed."""
    payload = [
        document.model_dump(mode="json", exclude_none=False)
        for document in sorted(documents, key=lambda item: item.id)
    ]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def metadata_signature(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return the comparable portion of persisted build metadata."""
    return {
        key: metadata.get(key)
        for key in (
            "schema_version",
            "corpus",
            "documents_fingerprint",
            "document_count",
            "embedding_provider",
            "embedding_model",
            "embedding_dimensions_requested",
            "azure_openai_embedding_deployment",
            "extraction_provider",
            "vector_backend",
            "max_edges_per_phrase",
        )
    }


def read_build_metadata(path: Path) -> dict[str, Any]:
    """Read persisted build metadata, returning an empty dict when unavailable."""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_build_metadata(path: Path, metadata: dict[str, Any]) -> None:
    """Persist index build metadata next to graph/vector artifacts."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
