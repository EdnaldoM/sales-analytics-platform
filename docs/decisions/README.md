# Architecture Decision Records (ADRs)

An ADR records **one significant decision**: the context that motivated it, the alternatives considered, the decision taken and its consequences. ADRs are **immutable**. When a decision changes, a new ADR supersedes the old one, and the old one is kept with status `Superseded by ADR-XXXX`. This preserves the history of *why* the platform looks the way it does.

## Index

| ADR | Title | Status | Date |
|---|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted | 2026-11-21 |
| [0002](0002-medallion-architecture-with-dimensional-gold.md) | Medallion architecture with a dimensional Gold layer | Accepted | 2026-11-21 |
| [0003](0003-use-snowflake-enterprise-as-data-warehouse.md) | Use Snowflake Enterprise as the data warehouse | Accepted | 2026-11-21 |
| [0004](0004-net-revenue-recognition-rules.md) | Net Revenue recognition rules | Accepted | 2026-11-21 |
| [0005](0005-simulate-sources-as-postgres-databases.md) | Simulate source systems as separate PostgreSQL databases | Accepted | 2026-11-21 |
| [0006](0006-cursor-based-incremental-ingestion.md) | Cursor-based incremental ingestion instead of CDC | Accepted | 2026-11-21 |
| [0007](0007-snowflake-configuration-as-versioned-sql.md) | Snowflake configuration as versioned SQL | Accepted | 2026-11-21 |
| [0008](0008-airflow-with-docker-compose.md) | Run Airflow locally with Docker Compose | Accepted | 2026-11-22 |
| [0009](0009-run-dbt-with-bashoperator-in-isolated-venv.md) | Run dbt from Airflow with BashOperator in an isolated virtualenv | Accepted | 2026-11-22 |
| [0010](0010-container-image-deployment-model.md) | Container image deployment model | Accepted | 2026-11-22 |
| [0011](0011-github-flow-and-semantic-versioning.md) | GitHub Flow and semantic versioning | Accepted | 2026-11-22 |
| [0012](0012-uv-and-make-for-local-tooling.md) | uv and Make for local tooling | Accepted | 2026-11-22 |
| [0013](0013-separate-sales-and-returns-facts.md) | Separate sales and returns facts | Accepted | 2026-11-21 |
| [0014](0014-customer-history-via-source-snapshot.md) | Customer history via a snapshot of the CRM source | Accepted | 2026-11-21 |
| [0015](0015-skip-pipeline-when-no-new-data.md) | Skip the pipeline when there is no new source data | Accepted | 2026-11-22 |

## Statuses

| Status | Meaning |
|---|---|
| Proposed | Under discussion |
| Accepted | Decided and in effect |
| Superseded by ADR-XXXX | Replaced by a later decision (kept for history) |
| Deprecated | No longer relevant, not replaced |

## Template

New ADRs copy this structure into `NNNN-short-title-in-kebab-case.md`:

```markdown
# ADR-NNNN: Title

- **Status:** Proposed | Accepted | Superseded by ADR-XXXX
- **Date:** YYYY-MM-DD
- **Related:** links to documents or other ADRs

## Context
The problem, constraints and forces at play. Facts, not opinions.

## Decision
What was decided, stated in one or two sentences, then the details.

## Alternatives considered
| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|

## Consequences
- Positive: ...
- Negative / trade-offs: ...
- Follow-up actions: ...

## References
Official documentation and sources consulted.
```
