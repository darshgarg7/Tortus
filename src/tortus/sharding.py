"""Toroidal shard-assignment simulation."""

import math
from dataclasses import dataclass

from .models import ConceptNode, ReasoningHop, TorusCoordinate


@dataclass(frozen=True)
class ShardAssignment:
    """Deterministic assignment of a node to a toroidal shard."""

    node_id: str
    shard_id: str
    row: int
    column: int


class ToroidalShardSimulator:
    """Deterministic topology-aware sharding over toroidal coordinates."""

    def __init__(self, rows: int = 4, columns: int = 4) -> None:
        """Initialize the toroidal shard grid."""
        if rows <= 0 or columns <= 0:
            raise ValueError("shard grid dimensions must be positive")
        self.rows = rows
        self.columns = columns

    def assign(self, node: ConceptNode) -> ShardAssignment:
        """Assign one node to a toroidal grid cell."""
        coordinate = node.torus or TorusCoordinate(theta=0.0, phi=0.0)
        column = min(self.columns - 1, int((coordinate.theta % math.tau) / math.tau * self.columns))
        row = min(self.rows - 1, int((coordinate.phi % math.tau) / math.tau * self.rows))
        return ShardAssignment(
            node_id=node.id,
            shard_id=f"shard:{row}:{column}",
            row=row,
            column=column,
        )

    def assignments(self, nodes: list[ConceptNode]) -> dict[str, ShardAssignment]:
        """Return shard assignments keyed by node id."""
        return {node.id: self.assign(node) for node in nodes}

    def fanout_for_nodes(self, nodes: list[ConceptNode]) -> int:
        """Return the number of unique shards touched by nodes."""
        return len({self.assign(node).shard_id for node in nodes})

    def fanout_for_node_ids(self, node_ids: list[str], nodes: list[ConceptNode]) -> int:
        """Return unique shard fanout for a set of node ids."""
        by_id = {node.id: node for node in nodes}
        touched = [by_id[node_id] for node_id in node_ids if node_id in by_id]
        return self.fanout_for_nodes(touched)

    def crossing_count(self, hops: list[ReasoningHop], nodes: list[ConceptNode]) -> int:
        """Count crossing count."""
        assignments = self.assignments(nodes)
        crossings = 0
        for hop in hops:
            source = assignments.get(hop.from_node)
            target = assignments.get(hop.to_node)
            if source and target and source.shard_id != target.shard_id:
                crossings += 1
        return crossings
