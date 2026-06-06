"""Vector index implementations for deterministic and scalable retrieval modes."""

import importlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from .models import ConceptNode, SearchHit


class VectorIndex(Protocol):
    """Common interface for Tortus vector indexes."""

    node_ids: list[str]
    labels: list[str]
    vectors: np.ndarray

    def search(self, query_vector: np.ndarray, top_k: int = 8) -> list[SearchHit]:
        """Search the index and return ranked node hits."""
        ...

    def save(self, path: Path) -> None:
        """Persist the index to disk."""
        ...


class ExactVectorIndex:
    """Small, deterministic baseline ANN stand-in using exact dot-product search."""

    def __init__(self, node_ids: list[str], labels: list[str], vectors: np.ndarray) -> None:
        """Initialize the in-memory exact vector index."""
        self.node_ids = node_ids
        self.labels = labels
        self.vectors = vectors.astype(np.float32)

    @classmethod
    def from_nodes(cls, nodes: list[ConceptNode], vectors: np.ndarray) -> "ExactVectorIndex":
        """Build an exact vector index from a list of ConceptNodes."""
        return cls([node.id for node in nodes], [node.label for node in nodes], vectors)

    def search(self, query_vector: np.ndarray, top_k: int = 8) -> list[SearchHit]:
        """Perform an exact dot-product search to find the nearest concept nodes."""
        if self.vectors.size == 0:
            return []
        query = query_vector.reshape(1, -1).astype(np.float32)
        scores = (self.vectors @ query.T).reshape(-1)
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [
            SearchHit(
                node_id=self.node_ids[index],
                label=self.labels[index],
                score=float(scores[index]),
            )
            for index in top_indices
        ]

    def save(self, path: Path) -> None:
        """Save the exact vector index to disk in a compressed npz format."""
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            vectors=self.vectors,
            node_ids=np.array(self.node_ids),
            labels=np.array(self.labels),
        )

    @classmethod
    def load(cls, path: Path) -> "ExactVectorIndex":
        """Load the exact vector index from disk."""
        data = np.load(path, allow_pickle=False)
        return cls(
            node_ids=[str(item) for item in data["node_ids"].tolist()],
            labels=[str(item) for item in data["labels"].tolist()],
            vectors=data["vectors"],
        )


class FaissVectorIndex:
    """Optional FAISS-backed index for larger corpora when faiss is installed."""

    def __init__(self, node_ids: list[str], labels: list[str], vectors: np.ndarray) -> None:
        """Initialize a flat inner-product FAISS index from normalized vectors."""
        faiss = importlib.import_module("faiss")
        self.node_ids = node_ids
        self.labels = labels
        self.vectors = vectors.astype(np.float32)
        self._index: Any = faiss.IndexFlatIP(self.vectors.shape[1])
        self._index.add(self.vectors)

    @classmethod
    def from_nodes(cls, nodes: list[ConceptNode], vectors: np.ndarray) -> "FaissVectorIndex":
        """Build a FAISS vector index from concept nodes."""
        ensure_faiss_available()
        return cls([node.id for node in nodes], [node.label for node in nodes], vectors)

    def search(self, query_vector: np.ndarray, top_k: int = 8) -> list[SearchHit]:
        """Search FAISS using inner-product similarity."""
        if self.vectors.size == 0:
            return []
        query = query_vector.reshape(1, -1).astype(np.float32)
        scores, indices = self._index.search(query, min(top_k, len(self.node_ids)))
        return [
            SearchHit(
                node_id=self.node_ids[int(index)],
                label=self.labels[int(index)],
                score=float(score),
            )
            for score, index in zip(scores[0], indices[0], strict=True)
            if int(index) >= 0
        ]

    def save(self, path: Path) -> None:
        """Save the FAISS index and metadata next to the requested path."""
        faiss = importlib.import_module("faiss")
        path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(path.with_suffix(".faiss")))
        path.with_suffix(".json").write_text(
            json.dumps({"node_ids": self.node_ids, "labels": self.labels}),
            encoding="utf-8",
        )
        np.savez_compressed(path.with_suffix(".vectors.npz"), vectors=self.vectors)

    @classmethod
    def load(cls, path: Path) -> "FaissVectorIndex":
        """Load a FAISS index and metadata from disk."""
        faiss = importlib.import_module("faiss")
        metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        vectors = np.load(path.with_suffix(".vectors.npz"), allow_pickle=False)["vectors"]
        instance = cls.__new__(cls)
        instance.node_ids = [str(item) for item in metadata["node_ids"]]
        instance.labels = [str(item) for item in metadata["labels"]]
        instance.vectors = vectors.astype(np.float32)
        instance._index = faiss.read_index(str(path.with_suffix(".faiss")))
        return instance


def ensure_faiss_available() -> None:
    """Raise a clear error if the optional FAISS dependency is unavailable."""
    if importlib.util.find_spec("faiss") is None:
        raise RuntimeError(
            "TORTUS_VECTOR_BACKEND=faiss requires the optional faiss package. "
            "Install faiss-cpu or switch TORTUS_VECTOR_BACKEND=exact."
        )


def vector_index_path(root: Path, backend: str) -> Path:
    """Return the index metadata path for a vector backend."""
    if backend == "faiss":
        return root / "vector_index.faiss.json"
    return root / "vector_index.npz"


def build_vector_index(
    backend: str,
    nodes: list[ConceptNode],
    vectors: np.ndarray,
) -> VectorIndex:
    """Build a vector index using the requested backend."""
    if backend == "exact":
        return ExactVectorIndex.from_nodes(nodes, vectors)
    if backend == "faiss":
        return FaissVectorIndex.from_nodes(nodes, vectors)
    raise ValueError(f"unknown vector backend: {backend}")


def load_vector_index(backend: str, path: Path) -> VectorIndex:
    """Load a vector index using the requested backend."""
    if backend == "exact":
        return ExactVectorIndex.load(path)
    if backend == "faiss":
        return FaissVectorIndex.load(path)
    raise ValueError(f"unknown vector backend: {backend}")
