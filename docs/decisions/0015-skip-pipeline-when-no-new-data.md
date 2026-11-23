# ADR-0015: Skip the pipeline when there is no new source data

- **Status:** Accepted
- **Date:** 2026-11-22
- **Related:** [data-flow.md](../architecture/data-flow.md#3-orchestration-flow-daily-pipeline)

## Context

Source activity is simulated by running the data generator manually or through a separate DAG. It is deliberately **not** part of the main pipeline, because a data platform does not control its source systems. On many scheduled runs there will be no new data.

Each run without new data would still wake up two Snowflake warehouses (ingestion and transformation) and consume credits for nothing.

## Decision

The first task of `sales_pipeline` is a **`ShortCircuitOperator`** (`check_new_source_data`). It compares high-water marks:
- **source**: `MAX(updated_at)` of the tracked PostgreSQL tables;
- **destination**: `MAX(updated_at)` of the same tables in `RAW`.

If no source table is newer than its copy in `RAW`, all downstream tasks are **skipped** and the run ends successfully.

The comparison reads the state of the data itself, so it stores nothing in Airflow and is **idempotent**. It stays correct even after manual Airbyte syncs.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Always run (no check) | Simplest; an incremental sync with no changes moves zero rows. But it consumes warehouse credits on every run, which matters on a trial or low-budget account. |
| Store the last processed timestamp in an Airflow Variable | Hidden state in the orchestrator that can drift from the real state (e.g. after a manual sync) |
| Run the generator as the first task of the pipeline | Unrealistic: source systems are independent of the data platform |
| Per-source checks (skip only unchanged sources) | More precise, but adds branching complexity; possible evolution |
| Airflow asset-aware / event-driven scheduling | Requires source systems to emit events; out of scope |

## Consequences

- Positive: no credits spent on empty runs (a FinOps decision); demonstrates short-circuiting and the `skipped` task state.
- Negative: the check is global. Any new data in any source triggers the full pipeline.
- Negative: the check needs read access to both PostgreSQL and Snowflake from Airflow (two connections).
- `ShortCircuitOperator` is part of Airflow's standard provider (`apache-airflow-providers-standard`), which ships with Airflow 3.
