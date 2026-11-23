# Getting Started

> **Status:** Planned (Stage 1). Each section is completed and validated in the stage that implements it · **Last updated:** 2026-11-22
>
> At this point the repository contains documentation only. There is nothing to run yet.

## 1. What runs where

| Runs locally (your machine) | Runs in the cloud (external services) |
|---|---|
| PostgreSQL (Docker Compose) | Snowflake: data warehouse |
| Data generator (Python, uv) | GitHub: repository, Actions (CI/CD), Container Registry |
| Airbyte (`abctl`) | |
| Airflow (Docker Compose) | |
| dbt (development) | |
| Power BI Desktop (Windows) | |

Local services are fully defined in the repository and rebuilt from it. External services need an account and a one-time configuration, described below.

## 2. Prerequisites

| Requirement | Version / note | Needed from stage |
|---|---|---|
| Windows 10/11 with **WSL2** and Ubuntu 24.04 | Tested environment. macOS/Linux should work but are not tested. | 2 |
| **RAM available to WSL ≥ 12 GB** | Airbyte alone needs ~8 GB. See [section 3](#3-wsl-configuration) | 3 |
| Docker Engine in WSL **or** Docker Desktop with WSL integration | Docker Compose v2+ | 2 |
| Git | 2.40+ | 1 |
| GitHub account with SSH key | — | 1 |
| GNU Make | Pre-installed on Ubuntu (`make --version`) | 2 |
| uv | Installs and pins Python itself | 2 |
| `abctl` (Airbyte CLI) | Pinned version, documented in Stage 3 | 3 |
| Snowflake account | **Enterprise** edition trial | 3 |
| Power BI Desktop | Windows only | 8 |

## 3. WSL configuration

WSL2 uses 50% of the Windows RAM by default. On a 16 GB machine that is ~8 GB, which is not enough to run Airbyte and Airflow together.

Create or edit `C:\Users\<windows-user>\.wslconfig`:

```ini
[wsl2]
memory=12GB
```

Then run `wsl --shutdown` in PowerShell and reopen the Ubuntu terminal. Validate with `free -h` (total ≈ 12 Gi).

| Machine RAM | Recommended `memory` |
|---|---|
| 16 GB | 12GB |
| 24 GB+ | Default is enough (~12 GB); 16GB if available |

## 4. Clone the repository

```bash
# Clone INSIDE the WSL filesystem (~), never under /mnt/c
cd ~
git clone git@github.com:EdnaldoM/sales-analytics-platform.git
cd sales-analytics-platform

# Repository-local Git identity (not versioned: repeat on every machine)
git config user.name  "<your name>"
git config user.email "<your personal or GitHub noreply email>"
```

**Why not under `/mnt/c`?** Files on the Windows disk are accessed through a translation layer: Docker bind mounts become very slow, and file permissions and line endings behave differently.

## 5. Local configuration *(Stage 2+)*

```bash
cp .env.example .env      # then fill in the values
```

| Variable group | Example variables | Notes |
|---|---|---|
| PostgreSQL | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_PORT` | Local only |
| Data generator | `GENERATOR_SEED`, `GENERATOR_ANCHOR_DATE` | Same values reproduce the same data |
| Snowflake | `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PRIVATE_KEY_PATH` | Stage 3 |
| Airbyte | `AIRBYTE_CLIENT_ID`, `AIRBYTE_CLIENT_SECRET` | Stage 3 |

`.env` is git-ignored. Never commit it.

## 6. External services setup

### 6.1. Snowflake *(Stage 3)*

1. Create a trial account at snowflake.com with a **personal email**. Choose **Enterprise** edition and AWS.
2. Run the versioned setup scripts in order (resource monitor, warehouses, databases, roles, users, grants).
3. Generate a key pair for each service user and for your developer user. Keep private keys outside the repository.

Detailed instructions are added in Stage 3.

### 6.2. GitHub Actions secrets *(Stage 7)*

Snowflake account identifier, CI and prod service users, private keys. Detailed list added in Stage 7.

### 6.3. Power BI *(Stage 8)*

Power BI Desktop connects to Snowflake with the `ANALYST` role. Instructions added in Stage 8.

## 7. Running the platform *(planned commands)*

| Step | Command | Stage |
|---|---|---|
| Install Python and dependencies | `make setup` | 2 |
| Start PostgreSQL | `make up` | 2 |
| Generate historical data | `make seed` | 2 |
| Generate incremental activity | `make simulate` | 2 |
| Install / start Airbyte | `make airbyte-up` | 3 |
| Apply Airbyte configuration | `make airbyte-apply` | 3 |
| Run dbt (development) | `make dbt-build` | 4 |
| Start Airflow | `make airflow-up` | 6 |
| Deploy a released Airflow image | `make deploy VERSION=vX.Y.Z` | 7 |
| Reset all local state | `make reset` | 2 |
| List all commands | `make help` | 2 |

## 8. Clean-clone acceptance test

The project is considered **reproducible** only after this checklist passes on the **second computer**, starting from an empty WSL home directory.

| # | Check | Expected result |
|---|---|---|
| CC-01 | Clone the repository and configure the local Git identity | Clone succeeds; `git config user.email` shows the personal email |
| CC-02 | Copy `.env.example` → `.env` and fill in the values | No other files needed outside Git (except private keys) |
| CC-03 | `make setup` | uv installs the pinned Python and dependencies from `uv.lock` |
| CC-04 | `make up` + `make seed` | PostgreSQL healthy; row counts match the documented volumes for the default seed |
| CC-05 | Airbyte installed and configuration applied | Sources, destination and connections created from versioned configuration |
| CC-06 | Run an Airbyte sync | Rows in `RAW`; counts match PostgreSQL |
| CC-07 | `make dbt-build` (dev target) | All models and tests pass |
| CC-08 | `make airflow-up` and trigger `sales_pipeline` | DAG run succeeds end to end |
| CC-09 | Run the pipeline again without new data | Downstream tasks skipped |
| CC-10 | Open the Power BI project and refresh | Dashboard loads; Net Revenue matches the reconciliation query |
| CC-11 | Governance tests T-G1 to T-G8 | All as expected ([data-governance.md](governance/data-governance.md#61-governance-acceptance-tests-stage-5)) |

Results are recorded in [PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md) and stored as evidence.

## 9. Troubleshooting

Known issues and fixes are added here as they are found during implementation.
