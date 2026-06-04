import math

from tortus.models import ConceptNode, TorusCoordinate
from tortus.sharding import ToroidalShardSimulator


def make_node(node_id: str, theta: float, phi: float) -> ConceptNode:
    return ConceptNode(
        id=node_id,
        label=node_id,
        text=node_id,
        chunk_id=f"{node_id}:chunk",
        document_id=f"{node_id}:doc",
        torus=TorusCoordinate(theta=theta, phi=phi),
    )


def test_shard_assignment_is_deterministic() -> None:
    simulator = ToroidalShardSimulator(rows=4, columns=4)
    node = make_node("n1", theta=math.pi, phi=math.pi)
    assert simulator.assign(node) == simulator.assign(node)


def test_shard_fanout_counts_unique_toroidal_shards() -> None:
    simulator = ToroidalShardSimulator(rows=4, columns=4)
    nodes = [
        make_node("n1", theta=0.1, phi=0.1),
        make_node("n2", theta=0.2, phi=0.2),
        make_node("n3", theta=math.tau - 0.1, phi=math.tau - 0.1),
    ]
    assert simulator.fanout_for_nodes(nodes) == 2
