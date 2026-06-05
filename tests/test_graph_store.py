import pytest

from tortus.graph_store import GraphStore
from tortus.models import ConceptNode, EdgeType, SemanticEdge


def test_graph_store_records_schema_version(tmp_path) -> None:
    store = GraphStore(tmp_path / "graph.sqlite3")
    try:
        assert store.schema_version() == "2"
        assert store.stats()["schema_version"] == 2
    finally:
        store.close()


def test_graph_store_rejects_edges_with_missing_nodes(tmp_path) -> None:
    store = GraphStore(tmp_path / "graph.sqlite3")
    try:
        store.upsert_nodes(
            [
                ConceptNode(
                    id="concept:a",
                    label="a",
                    text="a",
                    chunk_id="chunk:a",
                    document_id="doc:a",
                )
            ]
        )
        with pytest.raises(ValueError, match="missing"):
            store.upsert_edges(
                [
                    SemanticEdge(
                        id="edge:a-b",
                        source="concept:a",
                        target="concept:b",
                        edge_type=EdgeType.RELATED_TO,
                        weight=0.5,
                    )
                ]
            )
    finally:
        store.close()
