# ADR-0010: Container image deployment model

- **Status:** Accepted
- **Date:** 2026-11-22
- **Related:** [dataops-strategy.md](../dataops/dataops-strategy.md#7-continuous-delivery) · [ADR-0009](0009-run-dbt-with-bashoperator-in-isolated-venv.md)

## Context

"Putting dbt in production" means having a machine that, on a schedule and unattended, runs the **approved version** of the code with **pinned dependencies** and **production credentials**, and records logs and failures.

dbt itself uses little compute: it compiles SQL and sends it to Snowflake, where the processing happens. In companies, the always-on machine is usually in the cloud (dbt Cloud, managed Airflow, Kubernetes).

This project has no paid cloud infrastructure other than Snowflake. Two more constraints apply:
- GitHub-hosted runners are **ephemeral** (they exist only for one job);
- they **cannot reach** the local PostgreSQL and Airbyte.

## Decision

Deploy the orchestration layer as a **versioned container image**:

1. On a version tag, GitHub Actions **builds** the image (official Airflow + DAGs + dbt project + dbt virtualenv) and **pushes** it to the **GitHub Container Registry (GHCR)** as `sales-airflow:vX.Y.Z`.
2. The production host, which is the local machine playing the server role, **pulls** that version and restarts Airflow (`make deploy VERSION=vX.Y.Z`).
3. dbt model changes merged to `main` are also applied to the production warehouse by GitHub Actions (`cd-dbt`), which can reach Snowflake over the internet.

### Mapping to a cloud deployment

| Step | This project | Typical cloud equivalent |
|---|---|---|
| Build image | GitHub Actions | GitHub Actions / GitLab CI / Cloud Build |
| Registry | GHCR | AWS ECR, Google Artifact Registry, Azure ACR |
| Runtime | Docker Compose on a local machine | Managed Airflow (MWAA, Cloud Composer, Astronomer) or Kubernetes (Helm chart) |
| Rollout | Manual `pull` + restart | Automatic rollout triggered by the pipeline |
| Secrets | `.env` on the host + GitHub Secrets | AWS Secrets Manager, Vault, Kubernetes secrets |
| Sources reachability | Same machine | Private networking (VPC, VPN) to the source systems |

Most of the process (build, versioning, registry, configuration through environment variables) is identical. What changes is where the image runs and where the secrets are stored.

## Alternatives considered

| Alternative | Why not chosen |
|---|---|
| Run the code directly from the working copy (bind-mount the repository into Airflow) | Production would run whatever is checked out, not a reviewed version. Used for **development only**. |
| Schedule dbt with GitHub Actions cron | Possible for dbt alone, but the runner cannot reach Airbyte or PostgreSQL; it also mixes CI/CD with orchestration |
| dbt Cloud | Outside the dbt Core goal; paid beyond the developer tier |
| Managed Airflow in the cloud | Cost; out of scope for a local learning project |

## Consequences

- Positive: production runs an immutable, traceable version; rollback means deploying the previous tag; the pipeline is cloud-ready by design.
- Negative: the final rollout step is manual, and "production" is only available while the local machine is on. Both are accepted and documented.
