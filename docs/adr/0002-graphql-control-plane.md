# ADR 0002: Use GraphQL As The Retrieval Control Plane

## Decision

Tortus exposes concept lookup and answer retrieval through Strawberry GraphQL, while keeping graph storage and traversal as ordinary Python modules.

## Rationale

GraphQL gives callers a typed way to pass traversal policy, request reasoning paths, and inspect evidence without inventing a custom RPC format. It also keeps the API close to the project goal: retrieval should be inspectable and controllable, not hidden behind prompt-only behavior.

## Consequences

- The dashboard and external clients can share the same query surface.
- Future directives can encode budgets, local-only retrieval, and semantic group preferences.
- API tests are required because resolver behavior is part of the product contract.
