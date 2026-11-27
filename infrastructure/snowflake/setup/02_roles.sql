-- =============================================================================
-- 02 · Functional roles
-- Run as: USERADMIN (system role that creates users and roles)
-- Idempotent: safe to run again.
-- Design: docs/governance/data-governance.md (sections 2 and 3)
-- Docs: https://docs.snowflake.com/en/user-guide/security-access-control-considerations
-- =============================================================================

USE ROLE USERADMIN;

CREATE ROLE IF NOT EXISTS LOADER           COMMENT = 'Ingestion (Airbyte): owns the RAW source schemas';
CREATE ROLE IF NOT EXISTS TRANSFORMER      COMMENT = 'dbt development and CI: reads RAW, writes ANALYTICS_DEV';
CREATE ROLE IF NOT EXISTS TRANSFORMER_PROD COMMENT = 'dbt production (Airflow, deploy): the only role that builds ANALYTICS';
CREATE ROLE IF NOT EXISTS ANALYST          COMMENT = 'Read-only access to ANALYTICS.MARTS, PII masked';

-- Role hierarchy: SYSADMIN inherits every functional role. Recommended by
-- Snowflake so that the administrator can manage objects owned by these roles.
-- Users never receive SYSADMIN for daily work.
GRANT ROLE LOADER           TO ROLE SYSADMIN;
GRANT ROLE TRANSFORMER      TO ROLE SYSADMIN;
GRANT ROLE TRANSFORMER_PROD TO ROLE SYSADMIN;
GRANT ROLE ANALYST          TO ROLE SYSADMIN;

SHOW ROLES;
