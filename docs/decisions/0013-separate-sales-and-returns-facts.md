# ADR-0013: Separate sales and returns facts

- **Status:** Accepted
- **Date:** 2026-11-21
- **Related:** [data-model.md](../architecture/data-model.md#4-facts) · [ADR-0004](0004-net-revenue-recognition-rules.md)

## Context

The initial proposal was a single `fct_sales` at order-item grain. Returns, however, are separate business events:
- they happen weeks after the sale;
- they can be partial;
- one order item can be returned more than once;
- they affect revenue on the **refund date** ([ADR-0004](0004-net-revenue-recognition-rules.md)).

## Decision

Two transaction facts sharing conformed dimensions:

| Fact | Grain | Statuses included |
|---|---|---|
| `fct_sales` | One row per order item | **All** order statuses, with `is_recognized_sale` flag |
| `fct_returns` | One row per return item | Refunded returns only |

`fct_returns` carries both the refund date (primary role) and the original order date (cohort role), plus the dimension keys of the original sale.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Return columns on `fct_sales` (`returned_qty`, `refund_amount`) | Loses the refund date and multiple returns per item; old sales rows would have to be updated, mixing two event dates on one row |
| One event fact with sales and returns as signed rows (`event_type`) | Mixes different attributes and statuses in one table; every measure needs an event filter |
| `fct_sales` with recognized sales only | Cancelled Order Value would need a third fact; the recognition rule would be hidden in a filter instead of an explicit, testable column |
| Returns including non-refunded statuses | No metric uses them; they stay in Silver |

## Consequences

- Positive: each event keeps its own date and grain; both revenue views (financial and cohort) are supported; the model stays simple for Power BI (two facts, four shared dimensions).
- Negative: Net Revenue combines two facts. Sales and returns must be **aggregated separately** before being combined, or rows fan out ([metrics-definition.md](../business/metrics-definition.md#planned-sql-logic-monthly-net-revenue)).
