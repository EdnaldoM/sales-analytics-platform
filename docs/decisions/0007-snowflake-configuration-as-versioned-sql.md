# ADR-0007: Snowflake configuration as versioned SQL

- **Status:** Accepted
- **Date:** 2026-11-21
- **Related:** [ADR-0003](0003-use-snowflake-enterprise-as-data-warehouse.md) · [dataops-strategy.md](../dataops/dataops-strategy.md#10-configuration-as-code)

## Context

The Snowflake account needs warehouses, databases, schemas, roles, users, grants, a resource monitor and masking policies. The account is a time-limited trial and may need to be **recreated** from scratch. Configuration done by hand in the web UI would be lost and could not be reviewed.

## Decision

Manage all Snowflake account configuration as **ordered, idempotent SQL scripts** in the repository. They are applied by the administrator with SnowSQL / Snowflake CLI or a Snowsight worksheet.

- **Idempotent** means running a script twice gives the same result (`CREATE ... IF NOT EXISTS`, `CREATE OR ALTER`, `GRANT` statements that are safe to repeat).
- **Ordered** means numbered files (e.g. `01_resource_monitor.sql`, `02_warehouses.sql`, …) that respect dependencies.

**Planned improvement (after v1.0.0):** migrate these scripts to **Terraform** (Snowflake provider), treated as a scalability and drift-detection improvement.

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen now |
|---|---|---|---|
| Manual configuration in the UI | Fast to start | Not reproducible or reviewable; lost when the account is recreated | Fails reproducibility |
| **Versioned SQL scripts** ✅ | Uses Snowflake's own language; very transparent for learning; no additional tool | No state tracking: drift (manual changes) is not detected; removals must be scripted explicitly | — |
| Terraform (Snowflake provider) | Declarative; plan/apply; drift detection; industry standard for infrastructure | Another tool and state file to manage; hides the underlying SQL while learning | Planned as a later improvement once the SQL is understood |
| schemachange / other migration tools | Versioned migrations | Another tool; oriented to database objects rather than account configuration | Not needed at this scale |

## Consequences

- Positive: the account can be rebuilt in minutes; every privilege is reviewable in Git; strong learning value about Snowflake access control.
- Negative: drift is not detected automatically; discipline is required (no manual changes outside scripts).
- Follow-up: Terraform migration backlog item after v1.0.0.
