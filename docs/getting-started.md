# Getting Started

> **Status:** Stage 2 implemented (local source systems and data generator). Later sections are completed and validated in the stage that implements them · **Last updated:** 2026-11-27

## Quick start (new machine)

Follow the sections in order. Each step links to its details.

| # | Step | Where | Done once per… |
|---|---|---|---|
| 1 | Install WSL2 + Ubuntu, Git, Make, Docker Engine and uv | [2.1](#21-install-the-tools) | machine |
| 2 | Give WSL enough memory (needed from Stage 3) | [3](#3-wsl-configuration) | machine |
| 3 | Clone the repository and set the local Git identity | [4](#4-clone-the-repository) | clone |
| 4 | `make setup`: installs Python + dependencies, creates `.env` | [5](#5-local-configuration-stage-2) | clone |
| 5 | Edit `.env` and replace every `change-me` password | [5](#5-local-configuration-stage-2) | clone |
| 6 | `make up` → `make seed` → `make stats` → `make test` | [7.1](#71-source-systems-stage-2) | clone |

```bash
# Steps 3–6, after the tools are installed
cd ~
git clone git@github.com:EdnaldoM/sales-analytics-platform.git
cd sales-analytics-platform
git config user.name  "<your name>"
git config user.email "<your personal or GitHub noreply email>"
make setup        # creates .env: edit it now and replace every "change-me"
make up
make seed
make stats
make test
```

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

Only these tools are installed on the machine. Everything else (Python itself, Python packages, PostgreSQL, later Airbyte and Airflow) is installed by the project: Python packages into `.venv` by uv, services as Docker containers.

| Requirement | Minimum / note | Tested version (machine 1) | Needed from stage |
|---|---|---|---|
| Windows 10/11 with **WSL2** and Ubuntu 24.04 | macOS/Linux should work but are not tested | Ubuntu 24.04 | 2 |
| **RAM available to WSL ≥ 12 GB** | Airbyte alone needs ~8 GB. See [section 3](#3-wsl-configuration) | — | 3 |
| Docker Engine in WSL **or** Docker Desktop with WSL integration | Docker Compose v2+ | Engine 29.4.2 · Compose v5.1.3 | 2 |
| Git | 2.40+ | 2.43.0 | 1 |
| GitHub account with SSH key | — | — | 1 |
| GNU Make | Any 4.x. Not always present on a fresh WSL install | 4.3 | 2 |
| uv | 0.13+ (`required-version` in `pyproject.toml`). Installs Python 3.12 itself if missing | 0.13.9 | 2 |
| `abctl` (Airbyte CLI) | Pinned version, documented in Stage 3 | — | 3 |
| Snowflake account | **Enterprise** edition trial | — | 3 |
| Power BI Desktop | Windows only | — | 8 |

### 2.1. Install the tools

Commands from the official documentation. Run them once per machine; skip a tool if its version check already works.

**WSL2 + Ubuntu** (PowerShell as administrator, then restart Windows if asked):

```powershell
wsl --install -d Ubuntu-24.04
```

**Git and Make** (Ubuntu terminal):

```bash
sudo apt update
sudo apt install -y git make
git --version && make --version
```

**Docker Engine** ([official guide](https://docs.docker.com/engine/install/ubuntu/), apt repository method). Skip it if you use Docker Desktop with WSL integration instead.

```bash
# Add Docker's official GPG key
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update

# Install Docker Engine and the Compose plugin
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Run docker without sudo (post-install guide). Close and reopen the terminal afterwards
sudo usermod -aG docker $USER
```

Check in a new terminal: `docker run hello-world` and `docker compose version`. Membership in the `docker` group grants root-level access to the machine ([post-install guide](https://docs.docker.com/engine/install/linux-postinstall/)).

**uv** ([official guide](https://docs.astral.sh/uv/getting-started/installation/)). It installs into `~/.local/bin`, for your user only:

```bash
curl -LsSf https://astral.sh/uv/0.13.9/install.sh | sh   # tested version; drop "0.13.9/" for the latest
uv --version
```

Python does not need to be installed separately: `make setup` makes uv use a Python 3.12 that is already on the system, or download one.

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
make setup                # 1. uv creates .venv with Python 3.12 and the locked packages (uv.lock)
                          #    and copies .env.example to .env if .env does not exist yet
code .env                 # 2. open .env (or use nano) and replace every "change-me"
openssl rand -hex 16      #    generates a random password; run once per password
```

`make setup` runs `uv sync`, uv's equivalent of `python -m venv .venv` + `pip install -r requirements.txt`, with exact versions from `uv.lock`. Run it again after pulling changes to `pyproject.toml` or `uv.lock`. Without `make`, the same is `uv sync` + `cp .env.example .env`.

| Variable group | Variables | Notes |
|---|---|---|
| PostgreSQL | `POSTGRES_PORT`, `POSTGRES_PASSWORD`, `GENERATOR_PASSWORD`, `AIRBYTE_READER_PASSWORD` | Local only. Passwords are applied when the data volume is created; after changing them, run `make reset` |
| Data generator | `GENERATOR_SEED`, `GENERATOR_ANCHOR_DATE` | Empty = defaults (`42`, `2026-11-22`). Same values reproduce the same data |
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

## 7. Running the platform

### 7.1. Source systems *(Stage 2)*

Run from the repository root, in the WSL terminal:

```bash
make setup      # uv installs Python 3.12 and the locked dependencies; creates .env if missing
                # edit .env and replace every "change-me" password
make up         # start PostgreSQL and wait until it is healthy
make seed       # ~1.5 min: 24 months of history (deletes existing rows first)
make stats      # row counts per table
make simulate   # one run of new activity with real timestamps; repeat as often as you like
make test       # automated tests (~5 s, no database needed)
```

| Command | What it does | Repeatable? |
|---|---|---|
| `make seed` | Empties the three databases and rebuilds the history up to the anchor date. Same seed + same anchor date = identical data | Yes. It **discards** everything added by `simulate` |
| `make simulate` | One "tick" of activity: ~400 new orders, open orders and returns move to their next status, CRM segment changes, price and cost changes | Yes. Every run adds more. Not reproducible: it depends on the clock and the current data |
| `make psql DB=ecommerce` | Opens psql in one database (`ecommerce`, `crm` or `erp`) | — |
| `make reset` | Deletes the data volume and recreates empty databases (asks for confirmation) | — |

Expected counts after `make seed` with the defaults:

| Database | Table | Rows |
|---|---|---|
| ecommerce | `customers` · `orders` · `order_items` · `payments` | 50,000 · 400,000 · 1,004,208 · 434,234 |
| ecommerce | `returns` · `return_items` | 22,609 · 37,995 |
| crm | `customers` · `customer_contacts` | 48,115 · 83,749 |
| erp | `product_categories` · `products` · `product_cost_history` | 40 · 2,000 · 4,917 |

> **After Stage 3:** once Airbyte has synced the sources, a new `make seed` rewrites history with older `updated_at` values and reuses ids. Incremental syncs would miss it, so a re-seed must be followed by a full refresh of the Airbyte connections and of `RAW`.

### 7.2. Planned commands

| Step | Command | Stage |
|---|---|---|
| Install / start Airbyte | `make airbyte-up` | 3 |
| Apply Airbyte configuration | `make airbyte-apply` | 3 |
| Run dbt (development) | `make dbt-build` | 4 |
| Start Airflow | `make airflow-up` | 6 |
| Deploy a released Airflow image | `make deploy VERSION=vX.Y.Z` | 7 |
| List all commands | `make help` | 2 |

## 8. Clean-clone acceptance test

The project is considered **reproducible** only after this checklist passes on the **second computer**, starting from an empty WSL home directory.

| # | Check | Expected result |
|---|---|---|
| CC-01 | Clone the repository and configure the local Git identity | Clone succeeds; `git config user.email` shows the personal email |
| CC-02 | `make setup` | uv installs the pinned Python and dependencies from `uv.lock`; `.env` created from `.env.example` |
| CC-03 | Fill in `.env` | No other files needed outside Git (except private keys) |
| CC-04 | `make up` + `make seed` + `make test` | PostgreSQL healthy; row counts match [section 7.1](#71-source-systems-stage-2); all tests pass |
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

| Symptom | Cause | Fix |
|---|---|---|
| `make up` fails with "port is already allocated" | Another PostgreSQL (or old project container) uses port 5432 | Stop it (`docker ps`, then `docker stop <name>`), or set another `POSTGRES_PORT` in `.env` |
| `password authentication failed` after editing `.env` | Passwords are applied only when the volume is created | `make reset` (deletes the data), then `make seed` |
| Containers from other projects start again after `wsl --shutdown` | Their restart policy is `always` | `docker update --restart=no <name>` and `docker stop <name>` |
| `Missing .env` | `.env` is not versioned | `make setup`, then edit the passwords |
| PostgreSQL 18 ignores a volume mounted at `/var/lib/postgresql/data` | PostgreSQL 18+ images keep data in `/var/lib/postgresql/<major>/docker` | The Compose file mounts the volume at `/var/lib/postgresql` (already done) |
