# ADR-0006: Cursor-based incremental ingestion instead of CDC

- **Status:** Accepted
- **Date:** 2026-11-21
- **Related:** [source-systems.md](../architecture/source-systems.md) · [data-model.md](../architecture/data-model.md#6-incremental-strategy-facts)

## Context

Airbyte can replicate PostgreSQL incrementally in two ways:
- **cursor-based**: query rows where a cursor column (`updated_at`) is greater than the last saved value;
- **CDC (Change Data Capture)**: read the PostgreSQL write-ahead log through logical replication.

The sources receive inserts and updates. Volume is about 1,000 new order items per run, and the pipeline runs daily.

## Decision

Use **cursor-based incremental sync on `updated_at`** for every table. The sources follow two rules:
- `updated_at` is maintained by a **database trigger**;
- **no hard deletes** (status or soft-delete flags only).

The destination sync mode (*Incremental | Append + Deduped* vs *Incremental | Append*) and the exact definition of the Bronze tables are **pending validation in Stage 3**, after observing the connector behavior.

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|
| Full refresh | Simplest; always consistent | Reloads ~2M rows every run; wastes warehouse credits; no incremental learning | Inefficient |
| **Cursor-based incremental** ✅ | Simple; no database configuration; easy to explain and debug | Cannot detect hard deletes; depends on a reliable `updated_at`; misses intermediate states between syncs | — |
| CDC (logical replication) | Captures deletes and every intermediate change; low source load at high volume | Requires `wal_level=logical`, replication slots, a publication and extra privileges. An unconsumed slot retains WAL and can fill the disk. More operational complexity. | Its benefits (deletes, every intermediate state, high volume) are not needed here |

## Consequences

- Positive: simple, reproducible configuration; no special PostgreSQL settings.
- Negative: hard deletes would go unnoticed. Mitigated by the no-hard-delete rule (business assumption A-1).
- Negative: if a row changes twice between syncs, only the last state is captured. This is acceptable for daily analysis; the CRM snapshot captures history at the same granularity.
- CDC remains a documented alternative if deletes or intra-day history become requirements.

## References

- [Airbyte PostgreSQL source](https://docs.airbyte.com/integrations/sources/postgres)
- [Airbyte Snowflake destination: sync modes](https://docs.airbyte.com/integrations/destinations/snowflake)
