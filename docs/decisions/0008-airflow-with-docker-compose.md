# ADR-0008: Run Airflow locally with Docker Compose

- **Status:** Accepted
- **Date:** 2026-11-22
- **Related:** [architecture-overview.md](../architecture/architecture-overview.md)

## Context

Airflow 3 must run locally (WSL2), reproducibly on a second machine, alongside PostgreSQL and Airbyte, on machines with 16 GB and 24 GB of RAM. A key learning goal of the project is to understand **Docker and environment configuration** in depth.

## Decision

Run Airflow with the **official Apache Airflow Docker Compose file**, adapted to the project:
- **LocalExecutor**: no Celery workers, no Redis, fewer containers and less memory;
- a **custom image** extending the official image with project dependencies (see [ADR-0009](0009-run-dbt-with-bashoperator-in-isolated-venv.md));
- pinned image versions and environment variables from `.env`.

## Alternatives considered

| Alternative | Pros | Cons | Why not chosen |
|---|---|---|---|
| **Docker Compose (official file, LocalExecutor)** ✅ | Every service, volume, network and variable is explicit; no extra tooling; same mechanism used for PostgreSQL | More configuration to understand and maintain | — |
| Astro CLI (Astronomer) | Very easy (`astro dev start`); good developer experience | Abstracts Docker away; adds a vendor tool; less learning about the environment | Conflicts with the learning goal |
| Official Compose with CeleryExecutor (unchanged) | Closer to a distributed setup | More containers (Redis, workers) and memory; unnecessary for one machine | Resource cost without benefit |
| `pip install apache-airflow` directly in WSL | No Docker | Dependency conflicts; not reproducible; differs from deployment | Fails reproducibility |

## Consequences

- Positive: full understanding of the runtime; the same image is used locally and as the deployment artifact ([ADR-0010](0010-container-image-deployment-model.md)).
- Negative: the official Compose file is a **quick-start, not production-hardened**, as the Airflow documentation states. That is accepted here, and its production gaps (secrets backend, high availability, Kubernetes) are documented.

## References

- [Running Airflow in Docker](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/)
