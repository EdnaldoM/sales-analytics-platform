# Project Context

> Living document that keeps the technical context of the project across work sessions. **Updated at the end of every stage.**
>
> **Current stage:** 4 (dbt) · **Status:** Planning · **Last completed:** Stage 3 (`v0.3.0`) · **Last updated:** 2026-11-27

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

### 2.4. Stage 2: source systems and data generator

| # | Decision | Reference |
|---|---|---|
| D-33 | Image `postgres:18.7`; named volume mounted at `/var/lib/postgresql` (PostgreSQL 18+ layout); port bound to `127.0.0.1`; memory limit 1 GB; TCP healthcheck | `infrastructure/postgres/compose.yaml` |
| D-34 | Roles: `generator` owns databases and tables; `airbyte_reader` is read-only (`CONNECT`, `USAGE`, `SELECT` + default privileges); `PUBLIC` revoked | `infrastructure/postgres/init/` |
| D-35 | `updated_at` maintained by `BEFORE UPDATE` triggers `WHEN (OLD IS DISTINCT FROM NEW)`: no-op updates do not move the cursor | `infrastructure/postgres/init/` |
| D-36 | Generator as a Python package (`python -m data_generator`), Faker + psycopg; bulk load with `COPY`; one transaction per database; dependency groups in `pyproject.toml` | `data_generator/` |
| D-37 | Reproducibility: default seed `42`, anchor date `2026-11-22`; one independent random stream per domain (`random.Random("<seed>:<stream>")`) | `data_generator/config.py` |
| D-38 | Clean data first; quality issues Q1–Q12 injected in a separate step (`quality.py`) with explicit rates and its own random stream. Q8 and Q9 are inherent to the generation | `data_generator/quality.py` |
| D-39 | All time arithmetic in UTC; conversion to each system's convention only when a row is built (daylight saving time makes local wall-clock comparisons wrong) | `data_generator/timeutils.py` |
| D-40 | Coupon rounding residual goes to the item with the largest base, **the first one by line number on ties**. dbt must apply the same rule | [metrics-definition.md](docs/business/metrics-definition.md) |
| D-41 | Orders generated as monthly batches (Python generator) to keep memory low (~220 MB peak) | `data_generator/orders.py` |
| D-42 | `make simulate`: one "tick" per run with real timestamps (database defaults and triggers), three independent transactions, same quality issues as the history; not reproducible by design | `data_generator/simulate.py` |
| D-43 | Automated tests run on a small in-memory dataset, without a database: business rules on clean data, structural rules on data with issues | `tests/` |

### 2.5. Stage 3: Snowflake + Airbyte

| # | Decision | Reference |
|---|---|---|
| D-44 | Airbyte installed with `abctl` v0.30.4, chart/platform **2.6.0** pinned in the `Makefile` (`AIRBYTE_CHART_VERSION`) | `Makefile` |
| D-45 | Snowflake setup SQL run by the administrator in Snowsight (not Snowflake CLI); 5 ordered, idempotent scripts + read-only checks | [infrastructure/snowflake/](infrastructure/snowflake/README.md) |
| D-46 | `AIRBYTE_SVC`: `TYPE = SERVICE`, key-pair authentication (unencrypted PKCS#8, `chmod 600`, in `~/.snowflake/keys/`), role `LOADER`. dbt users follow the same pattern (Stages 4 and 7) | `05_users.sql` |
| D-47 | `RAW` schemas `ECOMMERCE`, `CRM`, `ERP`, `AIRBYTE_INTERNAL` created by the setup script and owned by `LOADER`; `LOADER` also has `CREATE SCHEMA` on `RAW` | `04_databases.sql` |
| D-48 | Airbyte reaches PostgreSQL through the `kind` Docker network as `sources-postgres:5432`; the published port stays bound to `127.0.0.1` | `Makefile` (`airbyte-network`) |
| D-49 | Account resource monitor: 20 credits per month (notify 50% and 75%, suspend 100%, suspend immediately 110%); warehouses X-Small, auto-suspend 60 s, statement timeout 1 h | `01_resource_monitor.sql`, `03_warehouses.sql` |
| D-50 | Sync mode *Incremental · Append + Deduped* (cursor `updated_at`, table primary key); dbt reads `RAW.<SYSTEM>.<TABLE>`; watermark `_AIRBYTE_EXTRACTED_AT`; Airbyte configured with Terraform; Airbyte kept, dlt documented as alternative (P-01, P-02, P-03, P-11) | [ADR-0016](docs/decisions/0016-airbyte-ingestion-configuration.md) |
| D-51 | Snowflake destination: `NUMBER(38,9)` for decimals and `trim_space = false` (connector defaults are `FLOAT` and `true`); internal schema `AIRBYTE_INTERNAL`; manual schedule until Stage 6; new source columns propagated | `infrastructure/airbyte/main.tf` |

## 3. Pending decisions

| # | Topic | Stage | Notes |
|---|---|---|---|
| ~~P-01~~ | ~~Airbyte destination sync mode and dbt source tables~~ | — | Resolved: Append + Deduped, final tables (D-50) |
| ~~P-02~~ | ~~Airbyte configuration as code~~ | — | Resolved: Terraform provider (D-50) |
| ~~P-03~~ | ~~Incremental watermark~~ | — | Resolved: `_AIRBYTE_EXTRACTED_AT` (D-50) |
| P-04 | `on_schema_change` setting for incremental models | 4 | |
| P-05 | Intermediate model materializations | 4 | |
| P-06 | Grants mechanism: future grants vs dbt `grants` config; column vs tag-based masking | 5 | |
| P-07 | Where the production `manifest.json` is stored for Slim CI | 7 | Artifact, release asset or Snowflake stage |
| P-08 | SQLFluff templater (`dbt` vs `jinja`); adoption of pre-commit | 7 | |
| P-09 | Confirm GitHub Free branch-protection and Actions-minutes rules for public repositories | 7 | |
| ~~P-10~~ | ~~Repository license~~ | — | Resolved: MIT (D-32) |
| ~~P-11~~ | ~~Ingestion tool~~ | — | Resolved: Airbyte kept, dlt documented in ADR-0016 (D-50) |

## 4. Repository structure

**Current (Stage 3):**

```text
.
├── README.md
├── PROJECT_CONTEXT.md
├── LICENSE
├── .gitignore · .gitattributes · .python-version · .env.example
├── Makefile                 make help
├── pyproject.toml · uv.lock
├── infrastructure/postgres/ compose.yaml + init/ (databases, roles, tables, grants)
├── infrastructure/snowflake/ README + setup/ (01–05) + checks/ (setup_check, row_counts)
├── infrastructure/airbyte/  Terraform: versions · variables · main · outputs + .terraform.lock.hcl + tf.sh
├── data_generator/          cli · config · catalog · records · timeutils · reference · orders
│                            quality · simulate · seed · db
├── tests/                   conftest + test_money · test_determinism · test_invariants
└── docs/
    ├── README.md
    ├── getting-started.md
    ├── business/        business-context.md · analytical-requirements.md · metrics-definition.md
    ├── architecture/    architecture-overview.md · data-flow.md · source-systems.md · data-model.md
    ├── governance/      data-governance.md
    ├── dataops/         dataops-strategy.md
    ├── modernization/   legacy-migration.md
    ├── decisions/       README.md + ADR 0001–0016
    └── diagrams/        architecture-overview.drawio.svg
```

**Target:** see [README.md](README.md#project-structure).

## 5. Tool versions

Versions are chosen and pinned in each stage after checking the official documentation.

| Tool | Version | Status / constraint |
|---|---|---|
| Python | 3.12 | Pinned via `.python-version`; `requires-python >=3.12,<3.13` |
| uv | 0.13.9 (machine 1) | `required-version >=0.13` |
| PostgreSQL image | `postgres:18.7` | Debian trixie based |
| Faker · psycopg[binary] | 40.63.0 · 3.3.9 | Group `generator`, locked in `uv.lock` |
| pytest · ruff | 9.2.0 · 0.17.6 | Group `dev`, locked in `uv.lock` |
| Airbyte `abctl` · platform (chart) | v0.30.4 · 2.6.0 | Local kind cluster; ingress-nginx 4.15.1 |
| Airbyte connectors | source-postgres 3.8.13 · destination-snowflake 5.2.3 | Pinned in the Terraform data sources; destination ≥ 5.x requires key pair or PAT |
| Terraform · provider `airbytehq/airbyte` | 1.17.2 (Docker image `hashicorp/terraform`) · 1.3.3 | Provider locked in `.terraform.lock.hcl` |
| Snowflake | Enterprise trial, AWS US East (N. Virginia) | Account created 2026-11-27 |
| dbt Core / dbt-snowflake | TBD (Stage 4) | dbt-snowflake ≥ 1.10.6 |
| Apache Airflow | TBD (Stage 6) | 3.x; Airbyte provider ≥ 6.x |
| Power BI Desktop | TBD (Stage 8) | |

**Documentation tooling used in Stage 1** (not part of the runtime):

| Tool | Version | Use |
|---|---|---|
| `minlag/mermaid-cli` (Docker) | 12.0.1 | Validate Mermaid diagrams |
| `rlespinasse/drawio-desktop-headless` (Docker) | v1.78.0 | Export `.drawio.svg` (run with `--shm-size=1g`) |
| Simple Icons | 16.38.1 | Technology logos |

**Development machine (machine 1):** Windows + WSL2 Ubuntu 24.04, 16 GB RAM (WSL limited to 12 GB by `.wslconfig`, ~11.7 GiB visible; 7.6 GiB by default), 12 CPUs, Docker Engine 29.4.2 (native in WSL), Docker Compose v5.1.3, Git 2.43.0, GNU Make 4.3, Python 3.12.3 (system). **Machine 2:** Windows + WSL2, 24 GB RAM.

## 6. Implementation status

| Stage | Status | Version |
|---|---|---|
| 1. Business, modeling, architecture | ✅ Done | `v0.1.0` |
| 2. Data generation | ✅ Done | `v0.2.0` |
| 3. Snowflake + Airbyte | ✅ Done | `v0.3.0` |
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
| 2026-11-23 | `e966cd2` | 1 | `docs: add MIT license (#1)` |
| 2026-11-23 | `e0ce9c8` | 2 | `build: local infrastructure for source systems (#2)` (PR A, squash) |
| 2026-11-24 | `6d47bee` | 2 | `feat: synthetic data generator for source systems (#3)` (PR B, squash: reference data, orders, quality issues, tests) |
| 2026-11-25 | `8d2c900` | 2 | `feat: source activity simulation and stage 2 docs (#4)` (tag `v0.2.0`) |
| 2026-11-27 | `91103f3` | 2 | `docs: add installation steps, tested versions and quick start (#5)` |
| 2026-11-27 | PR #6 | 3 | Snowflake setup scripts, Airbyte install, Airbyte configuration as code, stage 3 docs (tag `v0.3.0`) |

## 8. Tests and validations executed

| Date | Check | Result |
|---|---|---|
| 2026-11-22 | All 11 Mermaid diagrams rendered with mermaid-cli 12.0.1 | ✅ 11/11 OK |
| 2026-11-22 | Relative links in `docs/` resolve to existing files | ✅ (after Stage 1 files completed) |
| 2026-11-22 | Architecture diagram exported and visually reviewed | ✅ |
| 2026-11-24 | Full seed on a throwaway instance: time and memory | ✅ ~70–86 s, peak ~220 MB |
| 2026-11-24 | Reproducibility: re-seed with the same seed, md5 of every table | ✅ identical |
| 2026-11-24 | Order integrity: payment = items net + tax + shipping; returns only on delivered orders; returned ≤ sold; nothing after the anchor | ✅ 0 violations |
| 2026-11-24 | Business patterns: growth (Dec 2024 23.9k → Dec 2025 26.8k orders), Black Friday spike, top 10% customers = 46% of orders, 5% guests, AOV ~$312 | ✅ |
| 2026-11-24 | Quality issue rates vs plan (Q1 15.0%, Q2 30.0%, Q4 40.1%, Q5 2.99%, Q6 0.1%, Q7 0.5%, Q10 8/3/5%, Q11 459 rows, Q12 0.98%) | ✅ within plan |
| 2026-11-24 | `make test`: 26 tests | ✅ all pass (~5 s) |
| 2026-11-25 | `make simulate` × 9 after a seed: integrity checks above + no paid order without captured payment + one open cost row per product + valid cross-system references | ✅ 0 violations; 2–4 s per run |
| 2026-11-27 | Snowflake setup: scripts 01–05 + `setup_check.sql` | ✅ grants match the access matrix; `AIRBYTE_SVC` is `SERVICE` with key pair, no password |
| 2026-11-27 | Airbyte install (`abctl`, chart 2.6.0) and memory | ✅ ~20 min; ~4.7 GB RAM; `sources-postgres:5432` reachable from the cluster |
| 2026-11-27 | Test connection `erp` in the web UI: *Append* vs *Append + Deduped* | ✅ Append duplicates on cursor ties (2,011 rows / 2,000 keys); Deduped keeps rows = keys after simulate and after an empty sync |
| 2026-11-27 | `make airbyte-apply` then `make airbyte-plan` | ✅ 7 resources created; "No changes" |
| 2026-11-27 | Full load, 3 connections: counts `RAW` vs PostgreSQL (11 tables); money columns not `FLOAT`; SKUs with spaces kept | ✅ identical counts; 0 `FLOAT`; 14,916 SKUs with spaces (Q6 preserved) |
| 2026-11-27 | `make simulate` + incremental sync of the 3 connections (`row_counts.sql` vs `make stats`) | ✅ identical counts, `TOTAL_ROWS = DISTINCT_KEYS` on all 11 tables |

## 9. Known issues and observations

| # | Observation | Impact | Action |
|---|---|---|---|
| K-01 | Machine 1 has Docker images from previous projects (Airbyte 2.1.0, several Airflow images, `postgres:14`) | Possible port conflicts (8000, 8080, 5432) or an existing `abctl` installation | Check at Stages 2–3 before starting services |
| K-02 | WSL on machine 1 raised from 10 to 12 GB at Stage 3 | Airbyte uses ~4.7 GB; with Airflow (Stage 6) it may be tight | Stop Airbyte when not in use; measure again at Stage 6 |
| K-03 | Global Git identity on machine 1 is not the personal one | Wrong author on commits if the local config is missing | Repository-local `user.email` configured; repeat after every clone |
| K-04 | draw.io SVG export is ~1 MB (PNG fallbacks for HTML labels) | Larger file in Git | Accepted |
| K-05 | dbt and Power BI logos are not in Simple Icons | Diagram uses brand-colored labels | Accepted |
| K-06 | `make seed` after Airbyte syncs rewrites history with older `updated_at` values and reuses ids | Incremental syncs miss the change; `RAW` would mix two histories | After a re-seed: full refresh of the Airbyte connections and `RAW` (documented in getting-started) |
| K-07 | Default anchor date (2026-11-22) is in the past | No activity between the anchor and the first `make simulate` | Accepted: a realistic gap; or seed with `ANCHOR=<yesterday>` |
| K-08 | Simplifications in the synthetic data: state sales tax rates are approximate base rates; city names come from Faker and do not match the state | None for the analysis (region uses the state only) | Accepted, documented |
| K-09 | `make simulate` is not reproducible (clock and current data) | Results differ between runs and machines | By design; `--seed` fixes only the random choices |
| K-10 | Airbyte re-reads rows equal to the last cursor value; one simulate transaction gives many rows the same `updated_at` | A few rows (and all 40 categories) are re-sent on every sync | Harmless with Append + Deduped; dbt merges them again (ADR-0016) |
| K-11 | Terraform provider `airbytehq/airbyte` 1.3.3 on a self-managed Airbyte: the default token path returns the web UI (HTML); `cron_time_zone` is unknown after apply when not set | `failed to decode token response`; connections marked tainted | Workarounds in `infrastructure/airbyte/versions.tf` (`token_url`) and `main.tf` (`cron_time_zone = "UTC"`). Re-check when upgrading the provider |
| K-12 | Airbyte login email is `[not set]` after `abctl local install` | Confusing first login | `abctl local credentials --email <email>` |
| K-13 | Airbyte makes the machine slow (CPU at start-up, ~4.7 GB RAM) | Slower Windows while it runs | `make airbyte-down`; `wsl --shutdown` returns memory to Windows (getting-started, troubleshooting) |

## 10. Next activities

**Stage 4: dbt.** The plan is presented for approval before any implementation:

1. dbt Core + dbt-snowflake (≥ 1.10.6) in the uv project; profiles for dev (`ANALYTICS_DEV`, role `TRANSFORMER`) with key-pair authentication for the developer user.
2. Snowflake grants for dbt: `TRANSFORMER` / `TRANSFORMER_PROD` read `RAW`, write `ANALYTICS_DEV` / `ANALYTICS` (extend `infrastructure/snowflake/`).
3. Sources on `RAW.<SYSTEM>.<TABLE>` with freshness; staging models that clean quality issues Q1–Q12.
4. Intermediate models (identity resolution, coupon allocation, cost lookup), CRM snapshot, Gold star schema (`fct_sales`, `fct_returns`, dimensions).
5. Incremental facts with `merge` on `_AIRBYTE_EXTRACTED_AT` (data-model.md section 6); resolve P-04 and P-05.
6. Tests: generic, singular (reconciliation with metrics-definition.md), unit tests for the money rules.

## 11. How to resume in a new session

1. Read this file first, then [README.md](README.md) and the [ADR index](docs/decisions/README.md).
2. Check sections 3 (pending decisions), 9 (known issues) and 10 (next activities).
3. Working agreement:
   - every stage starts with a plan (objective, decisions, official documentation, alternatives, risks, deliverables, commit sequence) and **waits for approval**;
   - commits are executed by the project owner;
   - conversation in Portuguese, repository content in English.
