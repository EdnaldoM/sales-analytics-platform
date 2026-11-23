# Metrics Definition

> **Status:** Approved (Stage 1) · **Last updated:** 2026-11-21
>
> This document is the **single source of truth** for metric definitions. Business rules described here are implemented **once**, in the dbt Gold layer. Power BI measures only aggregate the resulting columns.
>
> SQL snippets are **planned logic** that illustrates the rules. The final implementation is delivered in Stage 4 and linked here.

## 1. General principles

| # | Principle |
|---|---|
| P-1 | **Currency:** all amounts are in USD, stored as `NUMBER(18,2)`. |
| P-2 | **Business timezone:** all dates used for reporting are converted to `America/New_York` before deriving the calendar date. |
| P-3 | **Revenue is recognized at order date**, for orders in a recognized status (section 2). |
| P-4 | **Returns reduce revenue on the refund date**, not on the original order date (official / financial view). |
| P-5 | **Taxes are excluded** from all revenue metrics. Sales tax is collected on behalf of the states and is not company revenue. |
| P-6 | **Shipping fees are excluded** from all revenue metrics. They are reported separately if needed. |
| P-7 | **Revenue is based on order items, not on payments.** Payments are used only for reconciliation and quality checks. |
| P-8 | Amounts are **always net of tax**, including refunds. |

## 2. Order status and revenue recognition

| Order status | Meaning | Counted in revenue? | Reported as |
|---|---|---|---|
| `pending_payment` | Order placed, payment not yet captured | ❌ No | — (excluded from all metrics) |
| `paid` | Payment captured | ✅ Yes | Sales |
| `shipped` | Order shipped | ✅ Yes | Sales |
| `delivered` | Order delivered | ✅ Yes | Sales |
| `cancelled` | Cancelled before shipment (whole order) | ❌ No | **Cancelled Order Value** |

In `fct_sales`, the flag `is_recognized_sale = order_status IN ('paid', 'shipped', 'delivered')`.

**Provisional recent periods.** An order can be cancelled after payment, up to shipment (usually within a few days). When that happens, the sale is removed from the **original order date**. Revenue for the most recent days is therefore **provisional** until the cancellation window closes. This is expected behavior, and the incremental models are designed to capture it (see [data-model.md](../architecture/data-model.md)).

## 3. Revenue components

### 3.1. Gross Revenue

**Definition.** Value of recognized items sold, at the price charged before any discount.

```
gross_amount = quantity × unit_price          (per order item)
Gross Revenue = SUM(gross_amount) WHERE is_recognized_sale
```

- `unit_price` is the **transactional price** charged at checkout, stored on the order item. It is **not** the current ERP list price, which may have changed since the sale.
- Excludes tax, shipping and cancelled orders.

### 3.2. Discounts

Cedar & Co. has two kinds of discount:

| Discount type | Source | Grain |
|---|---|---|
| Item discount | `order_items.item_discount_amount` | Order item |
| Order coupon | `orders.order_discount_amount` (with `coupon_code`) | Order |

Order coupons are **allocated to order items proportionally** to each item's value after its item discount. This keeps the fact table at item grain and lets coupon cost be analyzed by product and category.

```
item_base_i                     = gross_amount_i − item_discount_amount_i
allocated_order_discount_i      = order_discount_amount × item_base_i / SUM(item_base) over the order
discount_amount_i               = item_discount_amount_i + allocated_order_discount_i
Discounts                       = SUM(discount_amount) WHERE is_recognized_sale
```

**Rounding rule.** Allocations are rounded to 2 decimals. The rounding residual (at most a few cents) is assigned to the item with the largest `item_base` in the order, so allocations **sum exactly** to the order coupon. A dbt test enforces this.

### 3.3. Net Sales (intermediate measure)

```
net_sales_amount = gross_amount − discount_amount        (per order item)
```

Net Sales is the value effectively sold, before returns. It is the base for AOV and for refund calculation.

### 3.4. Returns

**Definition.** Value refunded to customers for returned items, **net of tax**, recognized on the **refund date**.

| Return status | Counted? |
|---|---|
| `requested`, `approved`, `received` | ❌ No (return in progress) |
| `rejected` | ❌ No (never refunded) |
| `refunded` | ✅ Yes, on `refunded_at` |

```
refund_amount = quantity_returned × (net_sales_amount / quantity)      (per return item, net of tax)
Returns       = SUM(fct_returns.refund_amount)                          (by refund date)
```

- A refund includes the discount effect: a customer who paid less gets less back.
- Partial returns are supported: `quantity_returned ≤ quantity` of the original item. This is enforced by a test, including the sum across several returns of the same item.
- Returns are attributed to the **product, customer and region of the original sale**.

### 3.5. Cancellations

Cancelled orders **never enter** Gross Revenue, so they are **not subtracted** from it. They are reported separately:

```
Cancelled Order Value = SUM(net_sales_amount) WHERE order_status = 'cancelled'
```

## 4. Primary metric: Net Revenue ⭐

```
Net Revenue = Gross Revenue − Discounts − Returns
```

| Component | Source | Date used | Included statuses |
|---|---|---|---|
| Gross Revenue | `fct_sales.gross_amount` | Order date | `paid`, `shipped`, `delivered` |
| Discounts | `fct_sales.discount_amount` | Order date | `paid`, `shipped`, `delivered` |
| Returns | `fct_returns.refund_amount` | **Refund date** | Return status `refunded` |
| ~~Taxes~~ | — | — | Excluded |
| ~~Shipping~~ | — | — | Excluded |
| ~~Cancellations~~ | — | — | Never included in Gross |

### Why returns use the refund date (official view)

| Option | Behavior | Decision |
|---|---|---|
| **Refund date (financial view)** | A return in March reduces March revenue. Closed periods never change because of returns. | ✅ **Official Net Revenue** |
| Original order date (cohort view) | A return in March reduces January revenue (the month of the sale). History is restated. | Available as an **analysis**, not as the official metric |

The cohort view is supported because `fct_returns` also carries the original `order_date_key`. In Power BI it is a secondary, inactive relationship, activated with `USERELATIONSHIP` in a dedicated measure.

### Planned SQL logic (monthly Net Revenue)

```sql
with sales as (
    select
        date_trunc('month', d.date)                   as month,
        sum(f.gross_amount)                           as gross_revenue,
        sum(f.discount_amount)                        as discounts
    from marts.fct_sales f
    join marts.dim_date d on f.order_date_key = d.date_key
    where f.is_recognized_sale                         -- recognition rule (section 2)
    group by 1
),
returns as (
    select
        date_trunc('month', d.date)                   as month,
        sum(r.refund_amount)                          as returns
    from marts.fct_returns r
    join marts.dim_date d on r.refund_date_key = d.date_key   -- refund date, not order date
    group by 1
)
select
    coalesce(s.month, r.month)                        as month,
    coalesce(s.gross_revenue, 0)                      as gross_revenue,
    coalesce(s.discounts, 0)                          as discounts,
    coalesce(r.returns, 0)                            as returns,
    coalesce(s.gross_revenue, 0)
      - coalesce(s.discounts, 0)
      - coalesce(r.returns, 0)                        as net_revenue
from sales s
full outer join returns r on s.month = r.month        -- a month may have returns but no sales
order by 1;
```

Key points:
- The two facts are **aggregated separately and then combined**. Joining `fct_sales` to `fct_returns` row by row and then summing would **duplicate sales amounts** (fan-out) when an item has more than one return.
- The `full outer join` keeps months that have returns but no sales.
- In Power BI, the same logic is expressed as separate measures over each fact, related through the shared `dim_date`.

## 5. Complementary metrics

| Metric | Definition | Formula | Notes |
|---|---|---|---|
| **Orders** | Number of distinct recognized orders | `COUNT(DISTINCT order_id) WHERE is_recognized_sale` | Based on order date |
| **AOV** (Average Order Value) | Average net value per recognized order | `SUM(net_sales_amount) / Orders`, recognized sales only | Uses Net Sales (before returns): returns happen in other periods and would distort the per-order average |
| **Revenue Growth MoM %** | Month-over-month change in Net Revenue | `(NR_month − NR_previous_month) / NR_previous_month` | Only complete months are compared |
| **Revenue Growth YoY %** | Year-over-year change in Net Revenue | `(NR_period − NR_same_period_last_year) / NR_same_period_last_year` | Requires 13+ months of history |
| **Gross Margin** | Net Revenue minus net cost of goods sold | `Net Revenue − (COGS sold − COGS returned)` | See below |
| **Gross Margin %** | Margin relative to Net Revenue | `Gross Margin / Net Revenue` | |
| **Return Rate** | Share of net sales that was refunded | `Returns / Net Sales` | Most meaningful in the cohort view (same order period) |
| **Discount Rate** | Discounts relative to Gross Revenue | `Discounts / Gross Revenue` | |
| **Cancelled Order Value** | See section 3.5 | | |

**Sales by Product / Customer / Category / Region** are not separate metrics. They are Net Revenue (and the metrics above) **sliced by a dimension**.

### Gross Margin and product cost

```
unit_cost         = ERP standard cost valid at the order date (product_cost_history)
cost_amount       = quantity × unit_cost                        (fct_sales)
returned_cost     = quantity_returned × unit_cost of the sale   (fct_returns)
COGS              = SUM(cost_amount WHERE is_recognized_sale) − SUM(returned_cost)
Gross Margin      = Net Revenue − COGS
```

- The cost is **frozen at the order date** using the ERP cost validity periods (`valid_from` ≤ order date < `valid_to`). Changing a cost later does not change historical margin.
- Returned items are assumed to go back to sellable inventory, so their cost is reversed. Damaged-goods write-offs are out of scope.

## 6. Worked example

One order placed on **2026-01-15**, coupon `WINTER10` worth **$19.00**, shipping **$7.99**, sales tax **8%**.

| Item | Qty | Unit price | Gross | Item discount | Item base | Allocated coupon | Discount total | Net sales | Tax (8%) | Unit cost | Cost |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | 2 | 50.00 | 100.00 | 10.00 | 90.00 | 9.00 | 19.00 | 81.00 | 6.48 | 20.00 | 40.00 |
| B | 1 | 100.00 | 100.00 | 0.00 | 100.00 | 10.00 | 10.00 | 90.00 | 7.20 | 45.00 | 45.00 |
| **Total** | | | **200.00** | 10.00 | 190.00 | **19.00** | **29.00** | **171.00** | 13.68 | | **85.00** |

Coupon allocation: A gets 19.00 × 90 / 190 = **9.00** and B gets 19.00 × 100 / 190 = **10.00**.

On **2026-02-10**, the customer returns **1 unit of item A**, refunded on **2026-02-12**: refund = 1 × (81.00 / 2) = **$40.50** (tax refunded separately, outside revenue). Returned cost = 1 × 20.00 = **$20.00**.

| Metric | January 2026 | February 2026 |
|---|---|---|
| Gross Revenue | 200.00 | 0.00 |
| Discounts | 29.00 | 0.00 |
| Returns (refund date) | 0.00 | 40.50 |
| **Net Revenue** | **171.00** | **−40.50** |
| COGS | 85.00 | −20.00 |
| Gross Margin | 86.00 | −20.50 |
| Orders / AOV | 1 / 171.00 | 0 / — |
| Cohort view: returns of January orders | 40.50 | — |

Not in any revenue metric: tax ($13.68) and shipping ($7.99). If the order had been cancelled before shipment, all revenue lines would be zero and **Cancelled Order Value** for January would be **$171.00**.

## 7. Data quality and reconciliation rules

These rules become dbt tests in Stage 4.

| # | Rule | Test type |
|---|---|---|
| DQ-01 | Allocated coupon per order equals the order coupon (to the cent) | Singular test |
| DQ-02 | Total quantity returned per order item ≤ quantity sold | Singular test |
| DQ-03 | Refunds only exist for items of recognized orders (cancelled orders cannot have refunds) | Singular test |
| DQ-04 | `gross_amount ≥ discount_amount ≥ 0` on every order item | Generic test |
| DQ-05 | Sum of captured payments per recognized order equals net sales + tax + shipping, within tolerance | Reconciliation test (Silver) |
| DQ-06 | Gold Gross Revenue equals the source order items total for recognized orders | Reconciliation test |
| DQ-07 | Every fact row has valid dimension keys (unknown members `-1` allowed) | `relationships` tests |
| DQ-08 | Unit cost exists for every sold product at the order date (warn if missing) | Generic test, severity `warn` |

## 8. Metric ownership

| Metric group | Business owner | Technical owner |
|---|---|---|
| Net Revenue, Gross Revenue, Discounts, Returns | Finance | Data team |
| Gross Margin | Finance | Data team |
| AOV, Orders, Growth | Commercial leadership | Data team |
| Cancelled Order Value, Return Rate | Commercial leadership / Category management | Data team |

Any change to a definition in this document requires an ADR and a version update of the affected dbt models and Power BI measures.
