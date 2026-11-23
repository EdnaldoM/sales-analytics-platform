# ADR-0009: Run dbt from Airflow with BashOperator in an isolated virtualenv

- **Status:** Accepted
- **Date:** 2026-11-22
- **Related:** [ADR-0008](0008-airflow-with-docker-compose.md) · [ADR-0010](0010-container-image-deployment-model.md)

## Context

Airflow must execute `dbt source freshness` and `dbt build` against Snowflake. Airflow and dbt are both Python applications with many dependencies. Installing them in the same Python environment can cause version conflicts that break one of them.

## Decision

- Install dbt Core and `dbt-snowflake` in a **dedicated virtualenv inside the custom Airflow image** (e.g. `/opt/dbt-venv`), separate from Airflow's Python environment.
- Copy the dbt project into the image.
- Call dbt from DAG tasks with **`BashOperator`** (e.g. `/opt/dbt-venv/bin/dbt build --target prod`).

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|
| dbt in the same environment as Airflow | Simplest | Dependency conflicts between Airflow and dbt | Fragile |
| **BashOperator + isolated virtualenv** ✅ | Simple; transparent (the command is exactly what a developer runs); no dependency conflicts; the image is a self-contained artifact | The whole `dbt build` is one Airflow task: model-level failures are visible in logs, not as separate tasks | — |
| Astronomer Cosmos | Renders each dbt model as an Airflow task; per-model retries and visibility | Additional library and concepts; heavier DAG parsing | Added complexity not needed initially; noted as a possible evolution |
| DockerOperator / KubernetesPodOperator (dbt in its own image) | Full isolation; the common production pattern on Kubernetes | Requires Docker-in-Docker or a Kubernetes cluster | Too complex for a local setup |
| dbt Cloud | Managed scheduling, IDE and CI | Paid beyond a single developer seat; outside the dbt Core learning goal | Requirement is dbt Core |

## Consequences

- Positive: one image contains everything needed to run the pipeline at a given version; dbt commands in production are identical to development.
- Negative: less granular visibility than Cosmos. Mitigated by dbt logs and `run_results.json`.
- Dependency versions for both environments are pinned and built into the image.
