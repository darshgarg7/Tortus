# ADR 0001: Use A Toroidal Layout For Locality Experiments

## Decision

Tortus keeps a two-dimensional toroidal coordinate for each concept node and uses torus distance during traversal scoring and shard simulation.

## Rationale

The project hypothesis is that wraparound locality may reduce artificial boundary effects for multi-hop retrieval. A torus is not assumed to be better than Euclidean space; it is a pluggable layout that can be compared against Euclidean and random layout probes.

## Consequences

- Traversal can reward nearby graph hops without treating chart edges as hard boundaries.
- Shard fanout and crossing metrics can be measured with the same coordinates.
- The benchmark must keep layout ablations so the torus claim stays falsifiable.
