# Data Governance: Quality and Security

> **Status:** Approved design (Stage 1). Implementation in Stage 4 (quality) and Stage 5 (security) · **Last updated:** 2026-11-22
>
> Related: [architecture-overview.md](../architecture/architecture-overview.md#43-roles-and-users) · [source-systems.md](../architecture/source-systems.md#8-pii-inventory) · [metrics-definition.md](../business/metrics-definition.md#7-data-quality-and-reconciliation-rules)
>
> Snowflake **Enterprise Edition** is required: masking policies, row access policies and tag-based masking are not available in Standard Edition.

## 1. Governance principles

| # | Principle |
|---|---|
| GP-1 | **Least privilege.** Every user and service gets only the access it needs, through roles. Privileges are never granted directly to users. |
| GP-2 | **Controls are enforced by the warehouse, not by the consumer.** Masking and access rules live in Snowflake, so they apply equally to Power BI, SQL clients and any future tool. |
| GP-3 | **Original data is preserved, access is restricted.** Raw keeps source values (including PII) for reprocessing and audit; consumption layers expose only what analysts need. |
| GP-4 | **Quality is tested continuously,** in CI and in every production run. A failing critical test stops the pipeline. |
| GP-5 | **Everything is versioned:** roles, grants, policies and tests are code in Git. |
| GP-6 | **Separate identities for humans and machines.** Service users use key-pair authentication; humans use their own users. |

## 2. Personas and roles

| Persona | Snowflake role | Purpose |
|---|---|---|
| Ingestion service | `LOADER` | Airbyte writes source data into `RAW` |
| dbt developer | `TRANSFORMER` | Develops and tests models in `ANALYTICS_DEV`; reads `RAW` and production (for `--defer`) |
| dbt production service | `TRANSFORMER_PROD` | The only identity allowed to build `ANALYTICS` (Airflow, CI/CD deploy) |
| Data analyst | `ANALYST` | Read-only access to the Gold layer (`ANALYTICS.MARTS`), PII masked |
| Platform administrator | `SYSADMIN` / `SECURITYADMIN` (system roles) | Creates objects and roles from the versioned SQL scripts. Not used for daily work. |

### 2.1. Users

| User | Type | Authentication | Default role | Default warehouse |
|---|---|---|---|---|
| `AIRBYTE_SVC` | `SERVICE` | Key pair | `LOADER` | `INGEST_WH` |
| `DBT_CI_SVC` | `SERVICE` | Key pair | `TRANSFORMER` | `TRANSFORM_WH` |
| `DBT_PROD_SVC` | `SERVICE` | Key pair | `TRANSFORMER_PROD` | `TRANSFORM_WH` |
| Developer (personal user) | `PERSON` | Password + MFA (web UI); key pair or browser SSO (dbt CLI) | `TRANSFORMER` | `TRANSFORM_WH` |
| `ANALYST_DEMO` | `PERSON` | Password + MFA | `ANALYST` | `REPORTING_WH` |

`TYPE = SERVICE` users cannot log in with a password or use the web UI. That is intended for machines, and it follows Snowflake's strong-authentication direction.

## 3. Access matrix

| Object | `LOADER` | `TRANSFORMER` | `TRANSFORMER_PROD` | `ANALYST` |
|---|---|---|---|---|
| `RAW.ECOMMERCE / CRM / ERP` | **Owner** (create, write) | Read | Read | ❌ None |
| `RAW.AIRBYTE_INTERNAL` | Owner | ❌ | ❌ | ❌ |
| `ANALYTICS.STAGING / INTERMEDIATE / SNAPSHOTS` | ❌ | Read | **Owner** | ❌ None |
| `ANALYTICS.MARTS` | ❌ | Read (PII visible) | **Owner** | **Read (PII masked)** |
| `ANALYTICS_DEV` | ❌ | **Owner** (create schemas) | ❌ | ❌ |
| `INGEST_WH` | Usage | ❌ | ❌ | ❌ |
| `TRANSFORM_WH` | ❌ | Usage | Usage | ❌ |
| `REPORTING_WH` | ❌ | ❌ | ❌ | Usage |

**Objects recreated by dbt.** dbt drops and recreates tables and views, so grants on individual objects would be lost. Grants are therefore given with **future grants** (`GRANT SELECT ON FUTURE TABLES IN SCHEMA ...`) and/or the dbt `grants` configuration. The choice is made in Stage 5.

## 4. PII protection

### 4.1. Controls by layer

| Point | Layer | Data state | Control |
|---|---|---|---|
| G1 | PostgreSQL sources | Clear text | Local, synthetic data; credentials only in `.env` (never committed) |
| G2 | `RAW` (Bronze) | **Clear text (preserved original)** | Access restricted to `LOADER`, `TRANSFORMER`, `TRANSFORMER_PROD`. Analysts have **no grant at all**. |
| G3 | `ANALYTICS` Silver | Normalized (needed for identity resolution) | No analyst access |
| G4 | `ANALYTICS.MARTS` (Gold) | Clear text stored, **masked at query time** | **Dynamic masking policies** on `dim_customer.email` and `dim_customer.phone` |
| G5 | Power BI | Masked | Connects with the `ANALYST` role, so it receives already-masked values. No masking logic in the BI layer. |
| G6 | Credentials | — | Key pairs for service users; private keys outside the repository; GitHub Secrets for CI/CD |

### 4.2. Dynamic data masking (planned design)

A masking policy is a SQL function attached to a column. Snowflake evaluates it **at query time** for the role running the query. The stored value never changes.

```sql
-- planned (Stage 5)
create masking policy governance.pii_email_mask as (val string) returns string ->
    case
        when is_role_in_session('TRANSFORMER_PROD') or is_role_in_session('TRANSFORMER')
            then val                                              -- data team: clear
        else regexp_replace(val, '^[^@]+', '*****')               -- others: *****@domain.com
    end;

alter table analytics.marts.dim_customer
    modify column email set masking policy governance.pii_email_mask;
```

| Column | Analyst sees | Why partial masking |
|---|---|---|
| `email` | `*****@gmail.com` | The domain still supports analysis (e.g. corporate vs personal email) without identifying the person |
| `phone` | `***-***-0100` (last 4 digits) | Common practice for customer-service verification; not identifying alone |

`IS_ROLE_IN_SESSION` is used instead of `CURRENT_ROLE()` so that the policy respects the **role hierarchy** (a role that inherits `TRANSFORMER` also sees clear values).

**Options evaluated in Stage 5:**

| Option | Description | When it is better |
|---|---|---|
| Column-level masking policy | Policy attached to each PII column | Few PII columns (our case) |
| **Tag-based masking** | Tag columns as `PII = 'email'`; the policy is attached to the **tag** | Many tables: new PII columns are protected just by tagging them |
| Secure views exposing only non-PII columns | Analysts query views, not tables | When some columns must be hidden entirely |
| Row access policies | Filter rows per role (e.g. a regional analyst sees only their region) | Not a current requirement. May be demonstrated as an extension. |

### 4.3. Hashing is not anonymization

Hashing is sometimes treated as "anonymizing" PII. In this project it is **not**.

| Technique | What it is | Reversible? | Personal data? |
|---|---|---|---|
| **Masking** (dynamic) | Hides the value for unauthorized roles at query time | Authorized roles see the original | Yes (stored in clear) |
| **Hashing** (`SHA2(email)`) | Deterministic one-way function | Not mathematically, but **emails are guessable**: anyone can hash a list of known emails and compare (dictionary attack) | **Yes: pseudonymized data** |
| **Salted / keyed hash** (HMAC with a secret) | Hash combined with a secret key | Only by whoever holds the key | Yes, pseudonymized (lower risk) |
| **Anonymization** | Irreversible removal of the link to a person, including through combination with other data | No | No |

A deterministic hash still lets an analyst **link the same person across datasets**, and with quasi-identifiers (city, postal code, purchase history) it can enable re-identification. That is why:
- the Gold layer uses **masking**, not hashing, for display;
- city and postal code are kept **out of Gold** (state only);
- if a hashed identifier is ever needed (e.g. to join datasets without exposing the email), it will be a **keyed hash** documented as pseudonymous.

### 4.4. Names

First and last names are personal data, but they are **not masked** in this project, by decision: the requirement defines email and phone as the PII to protect. Masking names would follow the same pattern (section 4.2) and can be added by tagging the columns.

## 5. Data quality

### 5.1. Test layers

| Layer | What is tested | Examples | Severity |
|---|---|---|---|
| **Sources** | Freshness and basic integrity of `RAW` | `dbt source freshness` (warn > 26 h, error > 50 h); `unique` / `not_null` on source primary keys | error |
| **Staging** | Cleaning worked | `unique` + `not_null` on every primary key; `accepted_values` on statuses; normalized email format | error |
| **Intermediate** | Business rules | Coupon allocation sums to the order coupon (DQ-01); identity resolution never maps one account to two CRM survivors | error |
| **Marts** | Model integrity and metrics | `relationships` from facts to dimensions (DQ-07); returned quantity ≤ sold (DQ-02); non-negative amounts (DQ-04) | error |
| **Reconciliation** | Gold matches the sources | Gross Revenue Gold vs source order items (DQ-06); payments vs order totals (DQ-05) | error / warn |
| **Expected anomalies** | Known source issues stay within expected limits | Orphan SKU rate (Q6) < 0.5%; unmatched customers < 35% | **warn** |

All rules DQ-01 to DQ-08 are listed in [metrics-definition.md](../business/metrics-definition.md#7-data-quality-and-reconciliation-rules).

**Severity policy.** `error` stops downstream models and fails the pipeline. `warn` is logged and reported but does not stop the run. It is used for known source issues that are handled by design (unknown members).

### 5.2. Test types used

| dbt feature | Use |
|---|---|
| Generic tests (`unique`, `not_null`, `accepted_values`, `relationships`) | Structural integrity on every model |
| Package tests (`dbt_utils`, e.g. `expression_is_true`, `unique_combination_of_columns`) | Business expressions and composite keys |
| Singular tests (SQL files in `tests/`) | Multi-row business rules (DQ-01, DQ-02, DQ-03) and reconciliation |
| Unit tests (dbt ≥ 1.8) | Complex logic tested with fixed inputs: coupon allocation, identity resolution, point-in-time join |
| Model contracts on Gold models | Guarantee column names and types consumed by Power BI; a breaking change fails the build instead of the dashboard |
| Source freshness | Detect stale ingestion |

### 5.3. Where tests run

| Context | Scope |
|---|---|
| Development | Developer runs `dbt build -s <model>+` |
| CI (pull request) | `dbt build` on modified models and their children (Slim CI) |
| Production (Airflow) | Full `dbt build` (models + tests) on every run |

## 6. Auditing and evidence

| Evidence | Source |
|---|---|
| Who queried which object | `SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY` (Enterprise) and `QUERY_HISTORY` |
| Login attempts | `SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY` |
| Grants in place | `SHOW GRANTS TO ROLE ...` (output saved as evidence) |
| Test results per run | dbt `run_results.json`, Airflow task logs |

### 6.1. Governance acceptance tests (Stage 5)

These tests prove the controls work. Their outputs (queries and screenshots) are stored as evidence.

| ID | As user / role | Action | Expected result |
|---|---|---|---|
| T-G1 | `ANALYST_DEMO` / `ANALYST` | `SELECT` from `RAW.CRM.CUSTOMER_CONTACTS` | ❌ Error: object does not exist or not authorized |
| T-G2 | `ANALYST_DEMO` / `ANALYST` | `SELECT` from `ANALYTICS.STAGING.*` | ❌ Error |
| T-G3 | `ANALYST_DEMO` / `ANALYST` | `SELECT email, phone FROM ANALYTICS.MARTS.DIM_CUSTOMER` | ✅ Rows returned, values **masked** |
| T-G4 | `TRANSFORMER` | Same query as T-G3 | ✅ Clear values |
| T-G5 | `TRANSFORMER` | `CREATE TABLE` in `ANALYTICS.MARTS` | ❌ Error: insufficient privileges |
| T-G6 | `LOADER` | `SELECT` from `ANALYTICS.MARTS` | ❌ Error |
| T-G7 | `AIRBYTE_SVC` | Login with password | ❌ Rejected (service user, key pair only) |
| T-G8 | Power BI connected as `ANALYST` | Show `email` column | Masked values |

## 7. Secrets management

| Secret | Stored in | Never in |
|---|---|---|
| PostgreSQL passwords (local) | `.env` (git-ignored) | Git, Docker images |
| Snowflake private keys | Outside the repository (e.g. `~/.snowflake/keys/`), path referenced in `.env` | Git, Docker images (mounted at runtime) |
| Snowflake keys for CI/CD | GitHub Actions encrypted secrets | Workflow files, logs |
| Airbyte API client credentials | `.env` / Airflow connection | Git |

`.env.example` documents every variable without values. Each machine generates **its own** key pair for the developer user; private keys are not copied between machines.
