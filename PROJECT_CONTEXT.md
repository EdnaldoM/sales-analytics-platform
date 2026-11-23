# Project Context

> Living document that keeps the technical context of the project across work sessions. **Updated at the end of every stage.**
>
> **Current stage:** 2 (Data generation) · **Status:** Planning · **Last completed:** Stage 1 (`v0.1.0`) · **Last updated:** 2026-11-23

## 1. Current architecture (summary)

```
Python/Faker → PostgreSQL (ecommerce, crm, erp) → Airbyte (cursor incremental)
  → Snowflake RAW (Bronze) → dbt: STAGING / INTERMEDIATE / SNAPSHOTS (Silver) → MARTS (Gold, star schema)
  → Power BI (role ANALYST, PII masked)
Orchestration: Airflow 3 (Docker Compose, LocalExecutor) · CI/CD: GitHub Actions + GHCR
```

Details: [docs/architecture/architecture-overview.md](docs/architecture/architecture-overview.md)

## 2. Approved decisions

### 2.1. Business and modeling

| # | Decision | Reference |
|---|---|---|
| D-01 | Fictional company **Cedar & Co.**: US online retailer, home & lifestyle goods, USD, state sales tax, timezone America/New_York | [business-context.md](docs/business/business-context.md) |
| D-02 | Net Revenue = Gross − Discounts − Returns; recognized at order date (`paid`, `shipped`, `delivered`) | [ADR-0004](docs/decisions/0004-net-revenue-recognition-rules.md) |
| D-03 | Cancelled orders excluded from Gross; reported as Cancelled Order Value | ADR-0004 |
| D-04 | Returns reduce revenue on the **refund date**, only when `refunded`, net of tax; cohort view available as analysis | ADR-0004 |
| D-05 | Order coupons allocated proportionally to items; shipping and tax excluded | ADR-0004 |
| D-06 | Gross Margin in scope, with cost from ERP `product_cost_history` | [ADR-0014](docs/decisions/0014-customer-history-via-source-snapshot.md) |
| D-07 | Region = order shipping state → census region (seed) | [data-model.md](docs/architecture/data-model.md) |
| D-08 | Source tables as documented, including e-commerce `customers`, `returns`, `return_items` and ERP `product_cost_history`; guest checkout (~5%) | [source-systems.md](docs/architecture/source-systems.md) |
| D-09 | 12 planned data quality issues (Q1–Q12); 24 months of history; ~1M order items | source-systems.md |
| D-10 | `fct_sales` (order item, all statuses + `is_recognized_sale`), `fct_returns` (refunded return items) | [ADR-0013](docs/decisions/0013-separate-sales-and-returns-facts.md) |
| D-11 | `dim_customer` anchored on the e-commerce account, enriched by CRM; SCD2 on segment via **snapshot of the CRM source**; CRM-only customers out of Gold | ADR-0014 |
| D-12 | Payments stay in Silver (reconciliation tests only); no aggregate marts initially | data-model.md |
| D-13 | Hash surrogate keys; unknown members `-1` | data-model.md |

### 2.2. Architecture and platform

| # | Decision | Reference |
|---|---|---|
| D-14 | Medallion architecture with dimensional Gold | [ADR-0002](docs/decisions/0002-medallion-architecture-with-dimensional-gold.md) |
| D-15 | **Snowflake Enterprise** trial (Databricks Free Edition rejected) | [ADR-0003](docs/decisions/0003-use-snowflake-enterprise-as-data-warehouse.md) |
| D-16 | Snowflake account created **only at the start of Stage 3**. After the trial: on-demand with a low cap, or a new account rebuilt from scripts | ADR-0003 |
| D-17 | Snowflake layout: databases `RAW`, `ANALYTICS`, `ANALYTICS_DEV`; warehouses `INGEST_WH`, `TRANSFORM_WH`, `REPORTING_WH`; roles `LOADER`, `TRANSFORMER`, `TRANSFORMER_PROD`, `ANALYST` | [architecture-overview.md](docs/architecture/architecture-overview.md#4-snowflake-layout) |
| D-18 | Snowflake configuration as versioned SQL; Terraform migration as a post-v1.0.0 improvement | [ADR-0007](docs/decisions/0007-snowflake-configuration-as-versioned-sql.md) |
| D-19 | PostgreSQL: one container, three databases | [ADR-0005](docs/decisions/0005-simulate-sources-as-postgres-databases.md) |
| D-20 | Cursor-based incremental ingestion on `updated_at`; no hard deletes | [ADR-0006](docs/decisions/0006-cursor-based-incremental-ingestion.md) |
| D-21 | Airflow with official Docker Compose (LocalExecutor), not Astro CLI | [ADR-0008](docs/decisions/0008-airflow-with-docker-compose.md) |
| D-22 | dbt run by BashOperator from an isolated virtualenv inside the Airflow image | [ADR-0009](docs/decisions/0009-run-dbt-with-bashoperator-in-isolated-venv.md) |
| D-23 | Deployment as a versioned image in GHCR, pulled by the local host | [ADR-0010](docs/decisions/0010-container-image-deployment-model.md) |
| D-24 | Source activity simulation outside the main DAG; `ShortCircuitOperator` skips runs without new data | [ADR-0015](docs/decisions/0015-skip-pipeline-when-no-new-data.md) |
| D-25 | PII = email and phone; partial dynamic masking in Gold; names not masked (documented) | [data-governance.md](docs/governance/data-governance.md) |

### 2.3. DataOps and tooling

| # | Decision | Reference |
|---|---|---|
| D-26 | GitHub Flow, squash merge, Conventional Commits, SemVer tag per stage | [ADR-0011](docs/decisions/0011-github-flow-and-semantic-versioning.md) |
| D-27 | Public repository from the first push | ADR-0011 |
| D-28 | uv for Python, Make as command entry point | [ADR-0012](docs/decisions/0012-uv-and-make-for-local-tooling.md) |
| D-29 | `.gitattributes` enforcing LF line endings | — |
| D-30 | Repository-local Git identity (personal email); the global Git identity of the machine is not used | — |
| D-31 | Diagrams: Mermaid for ERDs and flows; diagrams.net (`.drawio.svg`) for the architecture overview | [docs/README.md](docs/README.md#diagrams) |
| D-32 | MIT license; repository made public on 2026-11-23 | [LICENSE](LICENSE) |

## 3. Pending decisions

| # | Topic | Stage | Notes |
|---|---|---|---|
| P-01 | Airbyte destination sync mode (*Append + Deduped* vs *Append*) and which Airbyte tables are the dbt sources | 3 | Validate the connector's behavior first |
| P-02 | Airbyte configuration as code: API scripts vs Terraform provider | 3 | |
| P-03 | Incremental watermark: `_airbyte_extracted_at` vs source `updated_at` (current design: ingestion timestamp) | 3–4 | Validate column behavior |
| P-04 | `on_schema_change` setting for incremental models | 4 | |
| P-05 | Intermediate model materializations | 4 | |
| P-06 | Grants mechanism: future grants vs dbt `grants` config; column vs tag-based masking | 5 | |
| P-07 | Where the production `manifest.json` is stored for Slim CI | 7 | Artifact, release asset or Snowflake stage |
| P-08 | SQLFluff templater (`dbt` vs `jinja`); adoption of pre-commit | 7 | |
| P-09 | Confirm GitHub Free branch-protection and Actions-minutes rules for public repositories | 7 | |
| ~~P-10~~ | ~~Repository license~~ | — | Resolved: MIT (D-32) |

## 4. Repository structure

**Current (Stage 1):**

```text
.
├── README.md
├── PROJECT_CONTEXT.md
├── LICENSE
├── .gitignore
├── .gitattributes
└── docs/
    ├── README.md
    ├── getting-started.md
    ├── business/        business-context.md · analytical-requirements.md · metrics-definition.md
    ├── architecture/    architecture-overview.md · data-flow.md · source-systems.md · data-model.md
    ├── governance/      data-governance.md
    ├── dataops/         dataops-strategy.md
    ├── modernization/   legacy-migration.md
    ├── decisions/       README.md + ADR 0001–0015
    └── diagrams/        architecture-overview.drawio.svg
```

**Target:** see [README.md](README.md#project-structure).

## 5. Tool versions

No runtime component is pinned yet. Versions are chosen and pinned in each stage after checking the official documentation.

| Tool | Version | Status / constraint |
|---|---|---|
| Python | TBD (Stage 2) | Pinned via `.python-version` |
| PostgreSQL image | TBD (Stage 2) | |
| Airbyte (`abctl`, platform, connectors) | TBD (Stage 3) | Snowflake destination ≥ 5.x requires key pair or PAT |
| dbt Core / dbt-snowflake | TBD (Stage 4) | dbt-snowflake ≥ 1.10.6 |
| Apache Airflow | TBD (Stage 6) | 3.x; Airbyte provider ≥ 6.x |
| Power BI Desktop | TBD (Stage 8) | |

**Documentation tooling used in Stage 1** (not part of the runtime):

| Tool | Version | Use |
|---|---|---|
| `minlag/mermaid-cli` (Docker) | 12.0.1 | Validate Mermaid diagrams |
| `rlespinasse/drawio-desktop-headless` (Docker) | v1.78.0 | Export `.drawio.svg` (run with `--shm-size=1g`) |
| Simple Icons | 16.38.1 | Technology logos |

**Development machine (machine 1):** Windows + WSL2 Ubuntu 24.04, 16 GB RAM (7.6 GiB in WSL by default), 12 CPUs, Docker Engine 29.4.2 (native in WSL), Docker Compose v5.1.3, Git 2.43.0, GNU Make 4.3, Python 3.12.3 (system). **Machine 2:** Windows + WSL2, 24 GB RAM.

## 6. Implementation status

| Stage | Status | Version |
|---|---|---|
| 1. Business, modeling, architecture | ✅ Done | `v0.1.0` |
| 2. Data generation | Not started | |
| 3. Snowflake + Airbyte | Not started | |
| 4. dbt | Not started | |
| 5. Governance | Not started | |
| 6. Airflow | Not started | |
| 7. CI/CD | Not started | |
| 8. Power BI + final validation | Not started | |

## 7. Commits

Commits are executed by the project owner. This table records them after confirmation.

| Date | Commit | Stage | Description |
|---|---|---|---|
| 2026-11-22 | `93cb341` | 1 | `docs: define project scope, data model and architecture` (tag `v0.1.0`) |
| 2026-11-23 | *pending* | 1 | `docs: add MIT license` |

## 8. Tests and validations executed

| Date | Check | Result |
|---|---|---|
| 2026-11-22 | All 11 Mermaid diagrams rendered with mermaid-cli 12.0.1 | ✅ 11/11 OK |
| 2026-11-22 | Relative links in `docs/` resolve to existing files | ✅ (after Stage 1 files completed) |
| 2026-11-22 | Architecture diagram exported and visually reviewed | ✅ |

## 9. Known issues and observations

| # | Observation | Impact | Action |
|---|---|---|---|
| K-01 | Machine 1 has Docker images from previous projects (Airbyte 2.1.0, several Airflow images, `postgres:14`) | Possible port conflicts (8000, 8080, 5432) or an existing `abctl` installation | Check at Stages 2–3 before starting services |
| K-02 | WSL on machine 1 has 7.6 GiB RAM by default | Not enough for Airbyte + Airflow together | Set `.wslconfig` `memory=12GB` (Stage 3) |
| K-03 | Global Git identity on machine 1 is not the personal one | Wrong author on commits if the local config is missing | Repository-local `user.email` configured; repeat after every clone |
| K-04 | draw.io SVG export is ~1 MB (PNG fallbacks for HTML labels) | Larger file in Git | Accepted |
| K-05 | dbt and Power BI logos are not in Simple Icons | Diagram uses brand-colored labels | Accepted |

## 10. Next activities

**Stage 2: Data generation with Python and PostgreSQL.** The planning step is presented for approval before any implementation:

1. Docker fundamentals for this project: images, containers, Compose, volumes, networks, healthchecks.
2. PostgreSQL container: three databases, init scripts, `updated_at` triggers, read-only users for Airbyte.
3. uv project setup: Python version, dependencies, lockfile.
4. Generator design: seed control, anchor date, historical load vs incremental run, implementation of quality issues Q1–Q12.
5. Makefile: `setup`, `up`, `seed`, `simulate`, `reset`, `help`.
6. `.env.example`.
7. Validation: row counts, quality-issue rates, reproducibility (same seed → same data).

## 11. How to resume in a new session

1. Read this file first, then [README.md](README.md) and the [ADR index](docs/decisions/README.md).
2. Check sections 3 (pending decisions), 9 (known issues) and 10 (next activities).
3. Working agreement:
   - every stage starts with a plan (objective, decisions, official documentation, alternatives, risks, deliverables, commit sequence) and **waits for approval**;
   - commits are executed by the project owner;
   - conversation in Portuguese, repository content in English.
