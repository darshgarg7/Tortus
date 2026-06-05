"""High-level ingest, index, and engine-loading pipeline."""

from pathlib import Path

from .config import Settings
from .corpus import chunk_corpus, load_builtin_corpus, write_snapshot
from .embeddings import build_embedding_provider
from .extract import extract_graph
from .graph_store import GraphStore
from .models import ConceptNode
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
    }


def ingest_builtin(settings: Settings, corpus: str | None = None) -> tuple[int, int]:
    """Ingest a built-in corpus snapshot into the configured data directory."""
    corpus = corpus or settings.tortus_corpus
    documents = load_builtin_corpus(corpus)
    chunks = chunk_corpus(documents)
    write_snapshot(documents, chunks, data_paths(settings)["root"] / "corpus" / corpus)
    return len(documents), len(chunks)


def build_index(settings: Settings, corpus: str | None = None) -> dict[str, int]:
    """Build the graph store and vector index for a built-in corpus."""
    corpus = corpus or settings.tortus_corpus
    documents = load_builtin_corpus(corpus)
    chunks = chunk_corpus(documents)
    nodes, edges = extract_graph(chunks)
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
    graph.close()
    return stats


def load_engine(settings: Settings) -> QueryEngine:
    """Load a query engine, building persisted artifacts if needed."""
    paths = data_paths(settings)
    if not paths["graph"].exists() or not paths["index"].exists():
        build_index(settings)
    graph = GraphStore(paths["graph"])
    index = load_vector_index(settings.tortus_vector_backend, paths["index"])
    embeddings = build_embedding_provider(settings)
    return QueryEngine(graph=graph, index=index, embeddings=embeddings)


def load_nodes(settings: Settings) -> list[ConceptNode]:
    """Load all persisted concept nodes for the configured graph."""
    paths = data_paths(settings)
    if not paths["graph"].exists():
        build_index(settings)
    graph = GraphStore(paths["graph"])
    nodes = graph.list_nodes()
    graph.close()
    return nodes
