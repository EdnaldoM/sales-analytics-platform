# ADR-0014: Customer history via a snapshot of the CRM source

- **Status:** Accepted
- **Date:** 2026-11-21
- **Related:** [data-model.md](../architecture/data-model.md#52-customer-history-scd-type-2)

## Context

The CRM loyalty segment changes over time, but the CRM keeps only the current value. Business question BQ-12 requires revenue by segment **as it was at the time of purchase**.

Product cost also changes over time, but the ERP **already keeps** a cost history table with validity periods.

## Decision

| Attribute | History source | Technique |
|---|---|---|
| Customer segment (CRM) | **Captured by the platform** | dbt **snapshot** on the CRM source table (`timestamp` strategy on `updated_at`) feeding a **SCD Type 2** `dim_customer` |
| Product cost (ERP) | **Provided by the source** | `product_cost_history` joined by validity period, with the cost frozen on the fact at order date |
| Other customer and product attributes | Not needed | Type 1 (current value) |

Facts find the correct customer version with a **point-in-time join** (`order_ts` between `valid_from` and `valid_to`). The first version of each customer starts at `1900-01-01`, so that history before the first snapshot resolves to the earliest known version.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| No customer history (Type 1) | Past revenue would silently move to the customer's current segment; fails BQ-12 |
| Snapshot of an intermediate model | dbt recommends snapshotting sources: a snapshot of transformed data records changes caused by **logic fixes** as if they were business history |
| Product cost via a snapshot of `products` | History would exist only from the first snapshot run, so margin for the 24 months of history would use the current cost. The ERP cost history is the correct source. |
| SCD Type 2 on all customer attributes | No business question needs name or phone history; more versions without value |

## Consequences

- Positive: two history patterns are demonstrated (source-provided and platform-captured); margin is correct for the whole history.
- Negative / limitations:
  - snapshot history starts at its first run, so orders before it use the earliest known segment;
  - changes between two runs are not captured;
  - a customer matched to the CRM after its facts were loaded keeps the earlier key until the facts are fully refreshed.
- Follow-up: periodic full refresh of the facts ([dataops-strategy.md](../dataops/dataops-strategy.md#73-full-refresh-procedure)).
