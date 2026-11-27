# Snowflake account setup

Versioned SQL that builds the Snowflake account from scratch: resource monitor, roles, warehouses, databases and service users ([ADR-0007](../../docs/decisions/0007-snowflake-configuration-as-versioned-sql.md)). Design: [architecture-overview.md](../../docs/architecture/architecture-overview.md#4-snowflake-layout) and [data-governance.md](../../docs/governance/data-governance.md#3-access-matrix).

## How it works

The files are plain SQL. Snowflake executes them; any client can send them:

| Client | How | Used here |
|---|---|---|
| **Snowsight** (web interface) | Worksheet → paste or import the file → *Run All* | ✅ Setup is run once by the administrator, who logs in with MFA |
| Snowflake CLI | `snow sql -f setup/01_resource_monitor.sql` | No: one more tool and key setup for the admin user, for a one-off task |
| Terraform (Snowflake provider) | Declarative resources; the provider sends equivalent SQL | Planned after v1.0.0 (ADR-0007) |

Every script is **idempotent**: `CREATE ... IF NOT EXISTS` creates an object only once, `ALTER ... SET` re-applies its settings, and repeated `GRANT` statements change nothing. After editing a script, run it again; there is no need to delete anything first. Each script starts with `USE ROLE`, so it runs with the system role it needs, as long as your user has `ACCOUNTADMIN` (the trial's first user does).

| Order | File | Role | Creates |
|---|---|---|---|
| 1 | [setup/01_resource_monitor.sql](setup/01_resource_monitor.sql) | `ACCOUNTADMIN` | Monthly cap of 20 credits for the account |
| 2 | [setup/02_roles.sql](setup/02_roles.sql) | `USERADMIN` | `LOADER`, `TRANSFORMER`, `TRANSFORMER_PROD`, `ANALYST` |
| 3 | [setup/03_warehouses.sql](setup/03_warehouses.sql) | `SYSADMIN` | `INGEST_WH`, `TRANSFORM_WH`, `REPORTING_WH` (X-Small, auto-suspend 60 s) |
| 4 | [setup/04_databases.sql](setup/04_databases.sql) | `SYSADMIN` | `RAW` (+ schemas owned by `LOADER`), `ANALYTICS`, `ANALYTICS_DEV` |
| 5 | [setup/05_users.sql](setup/05_users.sql) | `USERADMIN` | `AIRBYTE_SVC` (service user) |
| — | [checks/setup_check.sql](checks/setup_check.sql) | `ACCOUNTADMIN` | Nothing: read-only checks with the expected results |
| — | [checks/row_counts.sql](checks/row_counts.sql) | `SYSADMIN` | Nothing: rows and duplicates per `RAW` table after an Airbyte sync |

## Steps

### 1. Run the setup scripts

In Snowsight: **Projects → Workspaces** (or **Worksheets**) → create a SQL file → paste the content of `01_resource_monitor.sql` → **Run All** (`Ctrl+Shift+Enter`). Repeat for files 2 to 5, in order.

### 2. Generate the key pair for `AIRBYTE_SVC` (WSL terminal)

Commands from the [Snowflake key-pair guide](https://docs.snowflake.com/en/user-guide/key-pair-auth). The private key never enters the repository (`.gitignore` blocks `*.p8` and `keys/`).

```bash
mkdir -p ~/.snowflake/keys && chmod 700 ~/.snowflake/keys
cd ~/.snowflake/keys
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out airbyte_svc.p8 -nocrypt   # private key
openssl rsa -in airbyte_svc.p8 -pubout -out airbyte_svc.pub                            # public key
chmod 600 airbyte_svc.p8
grep -v "PUBLIC KEY" airbyte_svc.pub | tr -d '\n'; echo                                # public key on one line
cd -
```

The private key is unencrypted (`-nocrypt`) and protected by file permissions (`600`: readable by your user only). An encrypted key would need a passphrase stored next to it, which adds a secret without adding protection on a single-user machine.

### 3. Register the public key

In a worksheet, run the commented statement at the end of `05_users.sql` with the one-line public key from step 2. Do not save the key in the file.

### 4. Check

Run `checks/setup_check.sql` and compare with the expected results in its comments.

## Rebuilding a new account

When the trial ends: create the new account, repeat steps 1 to 4, then update `SNOWFLAKE_ACCOUNT` in `.env`. A new key pair is optional; the same public key can be registered again.
