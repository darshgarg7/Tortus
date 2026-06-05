# ADR 0003: Use SQLite For The V1 Graph Store

## Decision

Tortus persists nodes, edges, schema metadata, and exported graph snapshots through a local SQLite store.

## Rationale

SQLite keeps the package easy to install and demo locally while still supporting durable storage, indexes, schema versioning, and validation checks. A heavier graph database would add operational complexity before the retrieval hypothesis is proven.

## Consequences

- Local demos and tests require no external service.
- The store can validate edge endpoints and expose schema metadata.
- Large-scale graph serving remains future work; v1 optimizes for reproducibility and package ergonomics.
