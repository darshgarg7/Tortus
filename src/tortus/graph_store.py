"""SQLite-backed semantic graph persistence."""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from .models import ConceptNode, EdgeType, SemanticEdge


class GraphStore:
    """Represent GraphStore data."""

    def __init__(self, path: Path) -> None:
        """Initialize a SQLite-backed graph store."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.create_schema()

    def create_schema(self) -> None:
        """Create create schema."""
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                weight REAL NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target);
            """
        )
        self.connection.commit()

    def upsert_nodes(self, nodes: list[ConceptNode]) -> None:
        """Upsert upsert nodes."""
        self.connection.executemany(
            "INSERT OR REPLACE INTO nodes(id, payload) VALUES (?, ?)",
            [(node.id, node.model_dump_json()) for node in nodes],
        )
        self.connection.commit()

    def upsert_edges(self, edges: list[SemanticEdge]) -> None:
        """Upsert upsert edges."""
        self.connection.executemany(
            """
            INSERT OR REPLACE INTO edges(id, source, target, edge_type, weight, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    edge.id,
                    edge.source,
                    edge.target,
                    edge.edge_type.value,
                    edge.weight,
                    edge.model_dump_json(),
                )
                for edge in edges
            ],
        )
        self.connection.commit()

    def get_node(self, node_id: str) -> ConceptNode | None:
        """Return get node."""
        row = self.connection.execute(
            "SELECT payload FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        return ConceptNode.model_validate_json(row["payload"]) if row else None

    def list_nodes(self) -> list[ConceptNode]:
        """Return list nodes."""
        rows = self.connection.execute("SELECT payload FROM nodes ORDER BY id").fetchall()
        return [ConceptNode.model_validate_json(row["payload"]) for row in rows]

    def list_edges(self) -> list[SemanticEdge]:
        """Return list edges."""
        rows = self.connection.execute("SELECT payload FROM edges ORDER BY id").fetchall()
        return [SemanticEdge.model_validate_json(row["payload"]) for row in rows]

    def neighbors(self, node_id: str, local_only: bool = False) -> list[SemanticEdge]:
        """Return neighbors."""
        rows = self.connection.execute(
            "SELECT payload FROM edges WHERE source = ? OR target = ?",
            (node_id, node_id),
        ).fetchall()
        edges = [SemanticEdge.model_validate_json(row["payload"]) for row in rows]
        if local_only:
            edges = [edge for edge in edges if edge.edge_type != EdgeType.PORTAL]
        return edges

    def adjacency(self) -> dict[str, list[SemanticEdge]]:
        """Return adjacency."""
        grouped: dict[str, list[SemanticEdge]] = defaultdict(list)
        for edge in self.list_edges():
            grouped[edge.source].append(edge)
            grouped[edge.target].append(
                edge.model_copy(update={"source": edge.target, "target": edge.source})
            )
        return dict(grouped)

    def stats(self) -> dict[str, int]:
        """Return stats."""
        node_count = self.connection.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
        edge_count = self.connection.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
        portal_count = self.connection.execute(
            "SELECT COUNT(*) AS c FROM edges WHERE edge_type = ?", (EdgeType.PORTAL.value,)
        ).fetchone()["c"]
        return {
            "nodes": int(node_count),
            "edges": int(edge_count),
            "portal_edges": int(portal_count),
        }

    def export_json(self, path: Path) -> None:
        """Return export json."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": [node.model_dump(mode="json") for node in self.list_nodes()],
            "edges": [edge.model_dump(mode="json") for edge in self.list_edges()],
            "stats": self.stats(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def close(self) -> None:
        """Close close."""
        self.connection.close()
