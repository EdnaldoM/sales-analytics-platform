# ADR-0005: Simulate source systems as separate PostgreSQL databases

- **Status:** Accepted
- **Date:** 2026-11-21
- **Related:** [source-systems.md](../architecture/source-systems.md)

## Context

Three independent operational systems (e-commerce, CRM, ERP) must be simulated locally with PostgreSQL in Docker. They can be separated by schema, by database or by container.

## Decision

**One PostgreSQL container with three databases**: `ecommerce`, `crm`, `erp`.

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|
| One database, three schemas | Simplest | Cross-schema joins and foreign keys are possible, which hides the integration problem; one Airbyte source for everything | Not realistic: real systems cannot join each other |
| **One container, three databases** ✅ | Cross-database joins impossible (like real systems); three independent Airbyte sources; one container to manage | Slightly more initialization scripting | — |
| Three containers | Full isolation (versions, credentials, ports) | 3× resources, ports and healthchecks; no extra learning value | Over-engineering for this goal |

## Consequences

- Positive: integration must happen in the warehouse, which is the problem the platform exists to solve. Each source has its own Airbyte connection, sync schedule and failure domain.
- Negative: PostgreSQL creates only one database by default; an initialization script creates the other databases (Stage 2).
- Each database gets its own read-only user for Airbyte (least privilege at the source).
