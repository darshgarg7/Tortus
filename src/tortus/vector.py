"""Exact vector index used as a deterministic baseline."""

from pathlib import Path

import numpy as np

from .models import ConceptNode, SearchHit


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
