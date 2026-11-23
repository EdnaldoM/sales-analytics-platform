# ADR-0004: Net Revenue recognition rules

- **Status:** Accepted
- **Date:** 2026-11-21
- **Related:** [metrics-definition.md](../business/metrics-definition.md)

## Context

Net Revenue is the primary metric. Several components could be treated in different ways, and each choice changes the numbers:
- the moment a sale counts,
- cancellations,
- returns that happen weeks later,
- order-level coupons,
- taxes and shipping.

## Decision

| Topic | Rule |
|---|---|
| Recognition | Revenue at **order date** for orders `paid`, `shipped` or `delivered` |
| Pending payment | Excluded |
| Cancellations | Never enter Gross Revenue; reported separately as **Cancelled Order Value** |
| Returns | Reduce revenue on the **refund date** (only `refunded` returns), net of tax and discounts |
| Order coupons | Allocated to items proportionally to item value after item discounts; rounding residual on the largest item |
| Taxes | Excluded from all revenue metrics |
| Shipping | Excluded from all revenue metrics |
| Revenue basis | Order items, not payments (payments used only for reconciliation) |
| Business timezone | America/New_York |

**Net Revenue = Gross Revenue − Discounts − Returns**

## Alternatives considered

| Topic | Alternative | Why not chosen |
|---|---|---|
| Returns | Attribute returns to the original order date (cohort view) | Restates closed periods every time a return is refunded. Kept as a **secondary analysis**, not the official metric. |
| Cancellations | Include in Gross, then subtract | Inflates Gross with sales that never happened |
| Recognition | At shipment or delivery date | Requires a shipment fact and delays revenue; order date is the common e-commerce convention |
| Coupons | Keep coupons at order level only | Breaks the item grain; coupon cost could not be analyzed by product or category |
| Taxes | Include in revenue | Sales tax is collected on behalf of the states; it is not company revenue |

## Consequences

- Positive: closed periods are stable; every component is explicit; coupon cost is analyzable by product.
- Negative: recent days are **provisional** until the cancellation window closes, because a cancellation removes revenue from the original order date.
- Negative: a negative Net Revenue is possible in a period with large refunds and few sales. This is correct under the financial view.
- Any change to these rules requires a new ADR and updates to the dbt models and Power BI measures.
