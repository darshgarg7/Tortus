# ADR 0004: Keep Exact Search As Default And Add Optional FAISS

## Decision

Tortus keeps exact NumPy dot-product search as the default vector backend and adds an optional FAISS backend selected with `TORTUS_VECTOR_BACKEND=faiss`.

## Rationale

Exact search is deterministic, dependency-light, and good for small corpora, tests, and benchmark reproducibility. FAISS is a better fit once the corpus grows, but making it mandatory would make the package harder to install.

## Consequences

- CI and tests can stay deterministic with the exact backend.
- Users with larger corpora can opt into FAISS when they install the optional dependency.
- Backend-specific benchmark results must name the backend used.
