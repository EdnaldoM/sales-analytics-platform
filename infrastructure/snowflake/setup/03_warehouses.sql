-- =============================================================================
-- 03 · Warehouses (compute): one per workload, all X-Small
-- Run as: SYSADMIN (creates and owns account objects)
-- Idempotent: CREATE ... IF NOT EXISTS, then ALTER re-applies the settings.
-- Design: docs/architecture/architecture-overview.md (section 4.2)
-- Docs: https://docs.snowflake.com/en/sql-reference/sql/create-warehouse
-- =============================================================================

USE ROLE SYSADMIN;

-- A suspended warehouse costs nothing: it is billed per second while running
-- (minimum 60 s each time it resumes). Separate warehouses cost nothing extra
-- and show the cost of each workload.

CREATE WAREHOUSE IF NOT EXISTS INGEST_WH    INITIALLY_SUSPENDED = TRUE;
CREATE WAREHOUSE IF NOT EXISTS TRANSFORM_WH INITIALLY_SUSPENDED = TRUE;
CREATE WAREHOUSE IF NOT EXISTS REPORTING_WH INITIALLY_SUSPENDED = TRUE;

ALTER WAREHOUSE INGEST_WH SET
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND = 60                       -- seconds idle before suspending
    AUTO_RESUME = TRUE                      -- starts by itself when a query arrives
    STATEMENT_TIMEOUT_IN_SECONDS = 3600     -- safety net against runaway queries
    COMMENT = 'Airbyte loads into RAW';

ALTER WAREHOUSE TRANSFORM_WH SET
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    STATEMENT_TIMEOUT_IN_SECONDS = 3600
    COMMENT = 'dbt in every environment (dev, CI, prod)';

ALTER WAREHOUSE REPORTING_WH SET
    WAREHOUSE_SIZE = XSMALL
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    STATEMENT_TIMEOUT_IN_SECONDS = 3600
    COMMENT = 'Power BI and analysts';

-- USAGE = permission to run queries on the warehouse.
GRANT USAGE ON WAREHOUSE INGEST_WH    TO ROLE LOADER;
GRANT USAGE ON WAREHOUSE TRANSFORM_WH TO ROLE TRANSFORMER;
GRANT USAGE ON WAREHOUSE TRANSFORM_WH TO ROLE TRANSFORMER_PROD;
GRANT USAGE ON WAREHOUSE REPORTING_WH TO ROLE ANALYST;

SHOW WAREHOUSES;
