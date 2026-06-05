"""SQLite-backed semantic graph persistence."""

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from .models import ConceptNode, EdgeType, SemanticEdge


class GraphStore:
    """SQLite-backed semantic graph store."""

    def __init__(self, path: Path) -> None:
        """Initialize a SQLite-backed graph store."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, check_same_thread=False)
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.row_factory = sqlite3.Row
        self.closed = False
        self.create_schema()

    def create_schema(self) -> None:
        """Create or migrate the graph schema."""
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS graph_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
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
            CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
            CREATE INDEX IF NOT EXISTS idx_edges_weight ON edges(weight);
            """
        )
        self.connection.execute(
            "INSERT OR REPLACE INTO graph_meta(key, value) VALUES ('schema_version', '2')"
        )
        self.connection.commit()

    def upsert_nodes(self, nodes: list[ConceptNode]) -> None:
        """Upsert concept nodes into the graph store."""
        self.connection.executemany(
            "INSERT OR REPLACE INTO nodes(id, payload) VALUES (?, ?)",
            [(node.id, node.model_dump_json()) for node in nodes],
        )
        self.connection.commit()

    def upsert_edges(self, edges: list[SemanticEdge]) -> None:
        """Upsert edges after validating their endpoint nodes exist."""
        known_nodes = {
            str(row["id"])
            for row in self.connection.execute("SELECT id FROM nodes").fetchall()
        }
        missing = sorted(
            {
                node_id
                for edge in edges
                for node_id in (edge.source, edge.target)
                if node_id not in known_nodes
            }
        )
        if missing:
            raise ValueError(f"edge endpoint(s) missing from graph nodes: {', '.join(missing[:5])}")
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
        """Return one concept node by id."""
        row = self.connection.execute(
            "SELECT payload FROM nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        return ConceptNode.model_validate_json(row["payload"]) if row else None

    def list_nodes(self) -> list[ConceptNode]:
        """Return all concept nodes sorted by id."""
        rows = self.connection.execute("SELECT payload FROM nodes ORDER BY id").fetchall()
        return [ConceptNode.model_validate_json(row["payload"]) for row in rows]

    def list_edges(self) -> list[SemanticEdge]:
        """Return all semantic edges sorted by id."""
        rows = self.connection.execute("SELECT payload FROM edges ORDER BY id").fetchall()
        return [SemanticEdge.model_validate_json(row["payload"]) for row in rows]

    def neighbors(self, node_id: str, local_only: bool = False) -> list[SemanticEdge]:
        """Return incident edges for a node, optionally excluding portal hops."""
        rows = self.connection.execute(
            "SELECT payload FROM edges WHERE source = ? OR target = ?",
            (node_id, node_id),
        ).fetchall()
        edges = [SemanticEdge.model_validate_json(row["payload"]) for row in rows]
        if local_only:
            edges = [edge for edge in edges if edge.edge_type != EdgeType.PORTAL]
        return edges

    def adjacency(self) -> dict[str, list[SemanticEdge]]:
        """Return an undirected adjacency map for traversal utilities."""
        grouped: dict[str, list[SemanticEdge]] = defaultdict(list)
        for edge in self.list_edges():
            grouped[edge.source].append(edge)
            grouped[edge.target].append(
                edge.model_copy(update={"source": edge.target, "target": edge.source})
            )
        return dict(grouped)

    def stats(self) -> dict[str, int]:
        """Return aggregate graph statistics."""
        node_count = self.connection.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
        edge_count = self.connection.execute("SELECT COUNT(*) AS c FROM edges").fetchone()["c"]
        portal_count = self.connection.execute(
            "SELECT COUNT(*) AS c FROM edges WHERE edge_type = ?", (EdgeType.PORTAL.value,)
        ).fetchone()["c"]
        return {
            "nodes": int(node_count),
            "edges": int(edge_count),
            "portal_edges": int(portal_count),
            "schema_version": int(self.schema_version()),
        }

    def schema_version(self) -> str:
        """Return the current graph schema version."""
        row = self.connection.execute(
            "SELECT value FROM graph_meta WHERE key = 'schema_version'"
        ).fetchone()
        return str(row["value"]) if row else "0"

    def export_json(self, path: Path) -> None:
        """Export the graph store to a JSON snapshot."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "nodes": [node.model_dump(mode="json") for node in self.list_nodes()],
            "edges": [edge.model_dump(mode="json") for edge in self.list_edges()],
            "stats": self.stats(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def close(self) -> None:
        """Close the underlying SQLite connection once."""
        if not self.closed:
            self.connection.close()
            self.closed = True
