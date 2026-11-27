# ADR-0016: Airbyte ingestion configuration

- **Status:** Accepted
- **Date:** 2026-11-27
- **Related:** [ADR-0006](0006-cursor-based-incremental-ingestion.md) · [infrastructure/airbyte/](../../infrastructure/airbyte/) · [infrastructure/snowflake/](../../infrastructure/snowflake/) · [data-model.md](../architecture/data-model.md#6-incremental-strategy-facts)

## Context

ADR-0006 chose cursor-based incremental ingestion and left four questions open for Stage 3, to be answered after observing the connectors:

| # | Question |
|---|---|
| P-01 | Destination sync mode: *Incremental · Append* or *Incremental · Append + Deduped*, and which tables dbt reads |
| P-02 | Airbyte configuration as code: scripts on the Airbyte API or the Terraform provider |
| P-03 | Incremental watermark for dbt: `_airbyte_extracted_at` or the source `updated_at` |
| P-11 | Ingestion tool: keep Airbyte or document dlt as the lightweight alternative |

A test connection (database `erp`, created in the web UI) was observed before the configuration was written as code. Versions: Airbyte 2.6.0 (`abctl` v0.30.4), source-postgres 3.8.13, destination-snowflake 5.2.3 (Direct Load), Terraform 1.17.2, provider `airbytehq/airbyte` 1.3.3.

## Observations

| # | Observation | Consequence |
|---|---|---|
| O-1 | Rows updated in the same PostgreSQL transaction share the same `updated_at` (the transaction start time). The connector **re-reads rows equal to the last cursor value** on the next sync. A sync with no source changes re-read 5 products, 10 cost rows and all 40 categories (seeded with one timestamp) | With *Append*, every re-read is a duplicate: after 3 syncs, `PRODUCTS` had 2,011 rows for 2,000 keys and `PRODUCT_CATEGORIES` 120 rows for 40 |
| O-2 | With *Append + Deduped*, `total rows = distinct keys` on every table after a full load, after `make simulate` + sync, and after a sync with no changes | Re-reads replace themselves |
| O-3 | `_AIRBYTE_EXTRACTED_AT` is set on every row a sync writes, including re-read rows that did not change in the source | A watermark on it also picks up re-read rows |
| O-4 | Destination defaults: `number_data_type = FLOAT` and `trim_space = true` | Money stored approximately; leading and trailing spaces removed, hiding quality issues Q1 (emails) and Q6 (SKUs) |
| O-5 | The internal schema defaults to `airbyte_internal`, created as a quoted lowercase identifier next to `AIRBYTE_INTERNAL` | Two internal schemas |
| O-6 | Final tables: uppercase table and column names (unquoted in SQL), typed columns plus `_AIRBYTE_RAW_ID`, `_AIRBYTE_EXTRACTED_AT`, `_AIRBYTE_META`, `_AIRBYTE_GENERATION_ID`; no raw tables (Direct Load) | dbt sources use plain identifiers |

## Decision

| # | Decision |
|---|---|
| P-01 | **Incremental · Append + Deduped**, cursor `updated_at`, primary key of each source table. `RAW` holds the **current state** of every source row, one row per key. History comes from dbt snapshots of `RAW.CRM.CUSTOMERS` ([ADR-0014](0014-customer-history-via-source-snapshot.md)). dbt reads the final tables `RAW.<SYSTEM>.<TABLE>`. |
| P-02 | **Terraform provider** (`infrastructure/airbyte/`), run from the official Terraform Docker image. Generic `airbyte_source` / `airbyte_destination` resources with the `airbyte_connector_configuration` data source, which validates the configuration against the connector spec during `plan`. State is local and git-ignored (it contains secrets). |
| P-03 | **`_AIRBYTE_EXTRACTED_AT`** stays the watermark for dbt incremental models. Re-read rows (O-3) are reprocessed by `merge` with the same result; the cost is a few rows per sync. The source `updated_at` is not used: CRM and ERP store it without a time zone (Q8). |
| P-11 | **Airbyte stays.** dlt is the recommended lightweight alternative (see below). |
| — | Destination settings: `NUMBER(38,9)` for decimals, `trim_space = false`, internal schema `AIRBYTE_INTERNAL` (O-4, O-5). Schedule: manual until Airflow triggers the syncs (Stage 6). New source columns are propagated; breaking schema changes stop the connection. |

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|
| *Incremental · Append* (P-01) | Keeps every captured version | Duplicates on every cursor tie (O-1); dbt must deduplicate everything; history only at sync granularity | The snapshot already provides the history that matters (customer segment) |
| Python scripts on the Airbyte public API (P-02) | No new tool; full control | Create-or-update logic, drift detection and deletes written by hand | Terraform gives `plan`, idempotent `apply` and drift detection for free; same tool as the planned Snowflake migration (ADR-0007) |
| Source `updated_at` as watermark (P-03) | Business meaning; no re-read rows | Local time without zone in CRM and ERP; a late-arriving row with an old `updated_at` would be missed | Ingestion time is monotonic and in UTC |
| **dlt** (P-11) | Python library, no server: runs inside an Airflow task; light (no ~5 GB Kubernetes footprint) | Connectors are code to maintain; no UI | Airbyte was an approved decision (D-20) and is common in the market. dlt is the first option if the local footprint becomes a problem |

## Consequences

- Positive: `RAW` mirrors the sources (one row per key), with exact decimals and untouched text; the configuration is reviewed in Git and recreated with `make airbyte-apply`.
- Positive: `make airbyte-plan` after an apply shows "No changes": the code describes exactly what exists.
- Negative: updates that happen between two syncs are not kept in `RAW` (only the last state). Accepted in ADR-0006.
- Negative: the Terraform state is local. If it is lost, an apply creates duplicates; the old objects must be deleted in the web UI first.
- Negative: provider 1.3.3 needs two workarounds, documented in `infrastructure/airbyte/`: an explicit `token_url` for a self-managed Airbyte, and `cron_time_zone` set even on a manual schedule.
- A re-seed after syncs requires a full refresh of the connections (K-06).

## References

- [Airbyte Snowflake destination](https://docs.airbyte.com/integrations/destinations/snowflake)
- [Airbyte PostgreSQL source](https://docs.airbyte.com/integrations/sources/postgres)
- [Incremental Append + Deduped](https://docs.airbyte.com/platform/using-airbyte/core-concepts/sync-modes/incremental-append-deduped)
- [Airbyte Terraform provider](https://registry.terraform.io/providers/airbytehq/airbyte/latest/docs)
- [dlt](https://dlthub.com/docs/intro)
