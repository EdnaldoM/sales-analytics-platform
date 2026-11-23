# Business Context

> **Status:** Approved (Stage 1) · **Last updated:** 2026-11-21
>
> Cedar & Co. is a **fictional company** created for this learning project. All data is synthetic. Any resemblance to real businesses is coincidental.

## 1. Company profile

| Attribute | Value |
|---|---|
| Name | Cedar & Co. |
| Segment | Home & lifestyle goods (kitchen, home décor, bedding, bath, outdoor) |
| Sales channel | Online store only (direct-to-consumer) |
| Market | United States, all 50 states + DC |
| Currency | USD |
| Taxes | State sales tax, collected at checkout on behalf of the states |
| Business timezone | America/New_York (headquarters) |
| Catalog size | ~2,000 active and discontinued products in ~40 categories |
| Customer base | ~50,000 online accounts; CRM also holds leads that never purchased online |
| Order volume | ~400,000 orders / ~1,000,000 order lines over 24 months |

The name refers to cedar wood, which is durable, aromatic and traditionally used in furniture and storage chests. It fits a home-goods retailer. "& Co." follows the classic retail naming convention.

## 2. Operational systems

Cedar & Co. runs three independent operational systems. Each one was implemented at a different time by a different team, so each has its own identifiers, naming conventions and data-entry practices.

| System | Owner | Purpose | Key entities |
|---|---|---|---|
| **E-commerce platform** | Digital team | Storefront, checkout, payments, returns | Customer accounts, orders, order items, payments, returns |
| **CRM** | Marketing / Customer Care | Customer relationship, loyalty segmentation, contact data | Customers, contacts (emails, phones), loyalty segment |
| **ERP** | Finance / Operations | Product master data, categories, standard costs | Products, categories, product cost history |

The full source data model is documented in [source-systems.md](../architecture/source-systems.md).

## 3. Business problem

Each team currently answers "how much did we sell?" from its own system, using its own spreadsheets and definitions:

- **Different revenue numbers for the same period.** The e-commerce team reports order totals, including tax and shipping. Finance reports revenue net of discounts and returns. Neither number reconciles with the other.
- **No consistent treatment of cancellations and returns.** Cancelled orders sometimes appear in sales reports. Returns are recorded weeks after the sale, and nobody agrees on which period they should affect.
- **Fragmented customer view.** An online account and its CRM record are linked only in about 70% of cases, so revenue by loyalty segment is unreliable.
- **No margin visibility.** Product costs live in the ERP and are not combined with sales.
- **No history.** When a customer's loyalty segment changes, reports silently re-attribute all of that customer's past revenue to the new segment.
- **Manual, error-prone process.** Reports are rebuilt by hand. There is no quality control, no access control over personal data, and no audit trail.

### Problem statement

> Cedar & Co. lacks a single, trusted and governed source of truth for **Net Revenue** and its components. As a result, teams cannot consistently measure commercial performance over time or by product, customer, category and region.

## 4. Business objectives

| # | Objective | How the platform supports it |
|---|---|---|
| BO-1 | Establish **one official definition of Net Revenue** shared by all teams | Metric rules documented in [metrics-definition.md](metrics-definition.md) and implemented once, in the dbt Gold layer |
| BO-2 | Monitor **sales performance over time** (daily, monthly, YoY) | Dimensional model with a calendar dimension; daily refreshed data |
| BO-3 | Explore performance **by product, category, customer segment and region** | Conformed dimensions shared by all facts |
| BO-4 | Understand **discount and return impact** on revenue | Discounts and returns modeled as explicit, separate components |
| BO-5 | Measure **gross margin** | Historical product costs combined with sales at order date |
| BO-6 | **Protect customer personal data** while enabling analysis | Role-based access and masking of PII in the consumption layer |
| BO-7 | Make reporting **automated, tested and reproducible** | Orchestrated pipeline, data tests, CI/CD and versioned infrastructure |

## 5. Stakeholders

| Stakeholder | Main interest | Typical questions |
|---|---|---|
| **Finance** | Official revenue, margin, period closing | What was Net Revenue last month? How much did returns reduce it? |
| **Commercial leadership** | Growth and performance trends | Are we growing year-over-year? Which regions are under-performing? |
| **Category management** | Product and category performance | Which categories drive revenue and margin? Which products are returned the most? |
| **Marketing / CRM** | Customer segments and promotions | How much revenue comes from each loyalty segment? What do discounts cost us? |
| **Data team** | Reliability, governance, maintainability | Is the data fresh and tested? Who can see personal data? |

The analytical needs of each stakeholder are detailed in [analytical-requirements.md](analytical-requirements.md).

## 6. Scope

### In scope

- Consolidation of the three operational systems into a cloud data warehouse.
- Net Revenue and its components (gross revenue, discounts, returns), plus cancelled order value, AOV, revenue growth, gross margin and return rate.
- Analysis by date, product, category, customer, customer segment and region (US state and census region).
- Data quality tests, access control and PII protection.
- Automated daily pipeline, CI/CD and a dashboard.

### Out of scope

- Inventory, logistics and fulfillment metrics (stock levels, delivery times).
- Marketing attribution and web analytics (sessions, conversion funnels).
- Physical stores and marketplace channels.
- Multi-currency and international sales.
- Payment-level financial reconciliation reports. Payments are used only as a data quality check (see [metrics-definition.md](metrics-definition.md#7-data-quality-and-reconciliation-rules)).
- Real-time / streaming analytics. Daily batch freshness meets the business need.
- Forecasting and machine learning.

## 7. Assumptions

| # | Assumption | Impact if false |
|---|---|---|
| A-1 | Operational systems never hard-delete records. They use status changes or soft-delete flags. | Cursor-based ingestion would miss deletions; CDC would be required |
| A-2 | Every source table has a reliable `updated_at` column, maintained on every change | Incremental ingestion would miss updates |
| A-3 | Orders can be cancelled only as a whole and only before shipment | Partial cancellations would require item-level cancellation status |
| A-4 | Returns are registered against specific order items, possibly for partial quantities | — |
| A-5 | The order shipping address represents the region of the sale | Region analysis would need a customer address source |
| A-6 | Product standard costs are maintained by Finance in the ERP with validity periods | Margin would need another cost source |
| A-7 | Daily data freshness is sufficient for all stakeholders | Near-real-time ingestion would be required |
