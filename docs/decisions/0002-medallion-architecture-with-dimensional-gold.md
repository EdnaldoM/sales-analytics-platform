# ADR-0002: Medallion architecture with a dimensional Gold layer

- **Status:** Accepted
- **Date:** 2026-11-21
- **Related:** [data-model.md](../architecture/data-model.md)

## Context

The platform integrates three operational sources with different identifiers, conventions and quality issues, and serves one analytical consumer (Power BI). It needs:
- clear responsibilities per processing step,
- the ability to reprocess from preserved source data, and
- a consumption model that business users and Power BI handle well.

## Decision

1. Organize the pipeline as a **Medallion architecture**:
   - **Bronze / Raw**: source copies, no business rules.
   - **Silver**: staging (clean, typed, standardized, deduplicated) and intermediate (integration and business rules), plus snapshots.
   - **Gold**: consumption models.
2. Model the Gold layer as a **Kimball star schema**: facts and conformed dimensions.

Medallion and dimensional modeling are complementary. Medallion defines the *refinement stages* of the pipeline. Dimensional modeling defines the *shape* of the Gold tables.

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|
| Single transformation layer (sources → reports) | Fewer models | Rules mixed with cleaning; no reuse; hard to test and debug | Fails maintainability and testability goals |
| One Big Table in Gold | Simple queries | Mixes grains (sales vs returns); repeated attributes; worse fit for Power BI | Return events have their own date and grain |
| 3NF / Inmon-style integrated layer in Gold | Strong integration | Many joins for analysis; does not represent business processes | Over-complex for consumers |
| Data Vault in Silver | Auditability, many changing sources | High modeling overhead | Three stable sources do not justify it |

## Consequences

- Positive: each layer has one responsibility and its own test focus; Raw allows full reprocessing; the star schema is the native shape for Power BI.
- Negative: more models to maintain than a single layer; developers must know which logic belongs in which layer (documented in [data-flow.md](../architecture/data-flow.md#2-what-happens-in-each-layer)).
