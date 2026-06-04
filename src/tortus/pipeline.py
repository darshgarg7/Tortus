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
from .vector import ExactVectorIndex


def data_paths(settings: Settings) -> dict[str, Path]:
    """Return data paths."""
    root = settings.tortus_data_dir
    return {
        "root": root,
        "corpus": root / "corpus" / "engineering",
        "graph": root / "graph.sqlite3",
        "index": root / "vector_index.npz",
        "graph_export": root / "graph.json",
    }


def ingest_builtin(settings: Settings, corpus: str = "engineering") -> tuple[int, int]:
    """Ingest ingest builtin."""
    documents = load_builtin_corpus(corpus)
    chunks = chunk_corpus(documents)
    write_snapshot(documents, chunks, data_paths(settings)["corpus"])
    return len(documents), len(chunks)


def build_index(settings: Settings) -> dict[str, int]:
    """Build build index."""
    documents = load_builtin_corpus("engineering")
    chunks = chunk_corpus(documents)
    nodes, edges = extract_graph(chunks)
    embeddings = build_embedding_provider(settings)
    node_vectors = embeddings.embed([node.label + "\n" + node.text for node in nodes])
    nodes = assign_torus(nodes, node_vectors)
    paths = data_paths(settings)
    graph = GraphStore(paths["graph"])
    graph.upsert_nodes(nodes)
    graph.upsert_edges(edges)
    graph.export_json(paths["graph_export"])
    ExactVectorIndex.from_nodes(nodes, node_vectors).save(paths["index"])
    stats = graph.stats()
    graph.close()
    return stats


def load_engine(settings: Settings) -> QueryEngine:
    """Load load engine."""
    paths = data_paths(settings)
    if not paths["graph"].exists() or not paths["index"].exists():
        build_index(settings)
    graph = GraphStore(paths["graph"])
    index = ExactVectorIndex.load(paths["index"])
    embeddings = build_embedding_provider(settings)
    return QueryEngine(graph=graph, index=index, embeddings=embeddings)


def load_nodes(settings: Settings) -> list[ConceptNode]:
    """Load load nodes."""
    paths = data_paths(settings)
    if not paths["graph"].exists():
        build_index(settings)
    graph = GraphStore(paths["graph"])
    nodes = graph.list_nodes()
    graph.close()
    return nodes
