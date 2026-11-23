# ADR-0003: Use Snowflake Enterprise as the data warehouse

- **Status:** Accepted
- **Date:** 2026-11-21
- **Related:** [architecture-overview.md](../architecture/architecture-overview.md) · [data-governance.md](../governance/data-governance.md)

## Context

The initial plan was **Databricks Free Edition**, to avoid a time-limited trial. Before committing, its limitations were checked against the project requirements: real governance with distinct personas, PII masking, and compatibility with Airbyte, dbt and Power BI.

Findings from the official Free Edition limitations page (checked 2026-11-21):
- Serverless compute only, with **one SQL warehouse limited to 2X-Small**.
- A daily quota: exceeding it shuts down compute for the rest of the day.
- One workspace and one metastore; **no account console or account-level APIs**; no SSO/SCIM.
- The page **does not state** whether service principals, additional users and groups, or column masks / row filters are available. These are the capabilities needed for the governance requirements.

Additional facts:
- The Airbyte Databricks destination recommends OAuth with a service principal (PAT as fallback).
- The connector had been rewritten recently (v4.0, July 2026).

## Decision

Use **Snowflake, Enterprise Edition**, on a 30-day trial account (AWS), created at the start of Stage 3 to make the most of the trial period.

| Requirement | Snowflake support |
|---|---|
| Distinct personas with least privilege | Native role-based access control; unlimited users, including `TYPE = SERVICE` users with key-pair authentication |
| PII masking | Dynamic data masking and tag-based masking (**Enterprise** edition required) |
| Row-level security (optional) | Row access policies (Enterprise) |
| Workload isolation and cost control | Multiple warehouses with auto-suspend; resource monitors |
| Airbyte | Mature Snowflake destination (v5.x), internal stage, key-pair authentication |
| dbt | `dbt-snowflake` adapter: merge, append, delete+insert, insert_overwrite, microbatch strategies; snapshots |
| Power BI | Native Snowflake connector (key-pair authentication supported) |
| Rollback and CI | Time Travel, zero-copy cloning |

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|
| Databricks Free Edition | No expiry; Unity Catalog; Delta | Unconfirmed support for service principals, extra users and masking; single 2X-Small warehouse shared by all workloads; daily quota shutdown | Governance requirements could not be guaranteed |
| Snowflake Standard Edition | Cheaper after the trial | No masking policies or row access policies | Fails the PII masking requirement |
| PostgreSQL as warehouse | Free, local | Not a cloud warehouse; no separation of storage/compute; limited governance features | Fails the learning objective (cloud architecture) |

## Consequences

- Positive: the governance requirements can be implemented natively; each workload gets its own warehouse; mature integrations with all tools.
- Negative: **the trial lasts 30 days or until the free credits are used**. After that the account is suspended until converted to on-demand billing.
  - Mitigation: the account is created only when needed (Stage 3), and **all Snowflake configuration is versioned SQL** ([ADR-0007](0007-snowflake-configuration-as-versioned-sql.md)), so a new account can be rebuilt quickly.
  - Post-trial options: convert to on-demand with a low resource monitor cap, or create a new account from the scripts.
- Negative: password-only authentication is being phased out by Snowflake, and the Airbyte connector already requires key pair or PAT. All service users use key-pair authentication from the start.
- Constraint: dbt-snowflake must be **≥ 1.10.6** because of a 2026 Snowflake column-size change.

## References

- [Databricks Free Edition limitations](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations)
- [Airbyte Databricks destination](https://docs.airbyte.com/integrations/destinations/databricks)
- [Snowflake trial accounts](https://docs.snowflake.com/en/user-guide/admin-trial-account)
- [Snowflake editions](https://docs.snowflake.com/en/user-guide/intro-editions)
- [Snowflake column-level security](https://docs.snowflake.com/en/user-guide/security-column-intro)
- [Snowflake MFA / strong authentication rollout](https://docs.snowflake.com/en/user-guide/security-mfa-rollout)
- [Airbyte Snowflake destination](https://docs.airbyte.com/integrations/destinations/snowflake)
- [dbt Snowflake configurations](https://docs.getdbt.com/reference/resource-configs/snowflake-configs)
