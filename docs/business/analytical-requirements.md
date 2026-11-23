# Analytical Requirements

> **Status:** Approved (Stage 1) · **Last updated:** 2026-11-21
>
> Related: [business-context.md](business-context.md) · [metrics-definition.md](metrics-definition.md) · [data-model.md](../architecture/data-model.md)

## 1. Business questions

The platform must answer the following questions. Each question is traced to the metrics and dimensions that answer it.

| ID | Question | Metrics | Dimensions |
|---|---|---|---|
| BQ-01 | What is Net Revenue per day, month, quarter and year? | Net Revenue | Date |
| BQ-02 | How is Net Revenue growing month-over-month and year-over-year? | Revenue Growth (MoM, YoY) | Date |
| BQ-03 | How does Gross Revenue break down into discounts, returns and Net Revenue? | Gross Revenue, Discounts, Returns, Net Revenue | Date |
| BQ-04 | Which products and categories generate the most Net Revenue and Gross Margin? | Net Revenue, Gross Margin, Gross Margin % | Product, Category |
| BQ-05 | Which customers and loyalty segments generate the most revenue? | Net Revenue, Orders, AOV | Customer, Customer Segment |
| BQ-06 | How does performance vary by US state and census region? | Net Revenue, Orders, AOV | Geography |
| BQ-07 | How much revenue is lost to returns, and which products have the highest return rate? | Returns, Return Rate | Product, Category, Date |
| BQ-08 | What is the value of cancelled orders? | Cancelled Order Value | Date, Geography |
| BQ-09 | What is the Average Order Value and how is it evolving? | AOV | Date, Customer Segment, Geography |
| BQ-10 | How much do discounts cost relative to Gross Revenue? | Discounts, Discount Rate | Date, Category |
| BQ-11 | For orders placed in a given month, how much was later returned? (cohort view) | Returns by order date | Date (order date role) |
| BQ-12 | How much revenue came from each loyalty segment **as it was at the time of purchase**? | Net Revenue | Customer Segment (historical) |

## 2. Metrics

All metric definitions, formulas and business rules live in [metrics-definition.md](metrics-definition.md). This table is the summary.

| Metric | Type | Priority |
|---|---|---|
| **Net Revenue** | Primary | ⭐ Primary metric |
| Gross Revenue | Component | High |
| Discounts | Component | High |
| Returns | Component | High |
| Cancelled Order Value | Complementary | Medium |
| Orders | Complementary | Medium |
| Average Order Value (AOV) | Complementary | Medium |
| Revenue Growth (MoM / YoY) | Complementary | Medium |
| Gross Margin / Gross Margin % | Complementary | Medium |
| Return Rate | Complementary | Low |
| Discount Rate | Complementary | Low |

## 3. Dimensions and hierarchies

| Dimension | Attributes | Hierarchy (drill path) | History |
|---|---|---|---|
| **Date** | Date, day of week, ISO week, month, quarter, year, weekend flag | Year → Quarter → Month → Day | — (static) |
| **Product** | SKU, name, brand, category, parent category, list price, active flag | Parent Category → Category → Product | Type 1 (current values) |
| **Customer** | Customer ID, name, email\*, phone\*, loyalty segment, CRM match method | Segment → Customer | **Type 2** for loyalty segment |
| **Geography** | State code, state name, census division, census region | Census Region → Division → State | — (static reference data) |

\* PII: masked for analysts. See [data-governance.md](../governance/data-governance.md).

**Date roles.** Sales are analyzed by **order date**. Returns are analyzed by **refund date** (official view) or by **original order date** (cohort view, BQ-11).

## 4. Granularity requirements

| Requirement | Required grain | Resulting design |
|---|---|---|
| Revenue by product | Order line (product level) | `fct_sales` at **order item** grain |
| Discounts, including order-level coupons | Order line | Coupons **allocated** to order lines |
| Returns on their own date, including partial returns | Return line | Separate `fct_returns` at **return item** grain |
| Orders count and AOV | Order | Count of distinct `order_id` in `fct_sales` |
| Daily trends | Day | `dim_date` at day grain |
| Region | US state | `dim_geography` at state grain, from shipping address |

The lowest required grain is the **order line**. Any coarser aggregate (day, month, category) can be derived from it, but not the reverse.

## 5. Functional requirements

| ID | Requirement |
|---|---|
| FR-01 | Integrate data from the e-commerce platform, the CRM and the ERP into a single analytical model |
| FR-02 | Calculate Net Revenue and all components according to [metrics-definition.md](metrics-definition.md) |
| FR-03 | Implement business rules once, in the transformation layer (dbt). The BI layer only aggregates. |
| FR-04 | Resolve customer identity between e-commerce accounts and CRM records |
| FR-05 | Map e-commerce order items to ERP products via standardized SKU |
| FR-06 | Preserve the history of customer loyalty segments (SCD Type 2) |
| FR-07 | Apply the product cost valid at the order date for margin calculation |
| FR-08 | Process updates to existing records: status changes, payment updates, late returns, segment changes |
| FR-09 | Represent unknown or unmatched members explicitly (guest checkout, orphan SKU, invalid state) instead of dropping rows |
| FR-10 | Provide a dashboard with filters by date, product, category, customer segment and region |
| FR-11 | Document every metric, model and column used by the dashboard |

## 6. Non-functional requirements

| ID | Category | Requirement | Target |
|---|---|---|---|
| NFR-01 | Freshness | Data available for analysis by the start of the business day | Daily batch; source freshness checked by dbt |
| NFR-02 | Data quality | Every model has primary key tests; critical business rules have dedicated tests | 100% of Gold models tested |
| NFR-03 | Reconciliation | Revenue in Gold reconciles with source order data | Automated reconciliation tests |
| NFR-04 | Security | Analysts cannot read Raw or Silver data; PII is masked for analysts | Enforced by warehouse roles and masking policies |
| NFR-05 | Idempotency | Re-running any pipeline step produces the same result | Incremental models with `unique_key`; deterministic surrogate keys |
| NFR-06 | Reprocessing | Late-arriving updates within the lookback window are captured; full rebuild is possible at any time | Lookback window + `--full-refresh` procedure |
| NFR-07 | Reproducibility | The whole project runs on a second computer from a clean clone | Clean-clone test documented in [getting-started.md](../getting-started.md) |
| NFR-08 | Cost | Cloud consumption kept to the minimum | Auto-suspended X-Small warehouses, resource monitor, incremental processing |
| NFR-09 | Maintainability | All changes go through version control, code review and CI | GitHub Flow with protected `main` |
| NFR-10 | Performance | Dashboard interactions respond in a few seconds | Power BI Import mode over a star schema |

## 7. Out of scope

Out-of-scope items are listed in [business-context.md](business-context.md#out-of-scope).
