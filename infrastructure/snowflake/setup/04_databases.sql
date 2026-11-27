-- =============================================================================
-- 04 · Databases, RAW schemas and ingestion grants
-- Run as: SYSADMIN
-- Idempotent: safe to run again.
-- Design: docs/architecture/architecture-overview.md (section 4.1)
--         docs/governance/data-governance.md (section 3, access matrix)
-- =============================================================================

USE ROLE SYSADMIN;

CREATE DATABASE IF NOT EXISTS RAW           COMMENT = 'Bronze: source data as loaded by Airbyte';
CREATE DATABASE IF NOT EXISTS ANALYTICS     COMMENT = 'Silver and Gold, built by dbt production';
CREATE DATABASE IF NOT EXISTS ANALYTICS_DEV COMMENT = 'dbt development and CI schemas';

-- -----------------------------------------------------------------------------
-- RAW: one schema per source system, plus Airbyte's internal schema.
-- The schemas are created here (not by Airbyte) so that their owner is LOADER
-- and later grants to dbt can be given per schema, leaving AIRBYTE_INTERNAL out.
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS RAW.ECOMMERCE        COMMENT = 'PostgreSQL database ecommerce';
CREATE SCHEMA IF NOT EXISTS RAW.CRM              COMMENT = 'PostgreSQL database crm';
CREATE SCHEMA IF NOT EXISTS RAW.ERP              COMMENT = 'PostgreSQL database erp';
CREATE SCHEMA IF NOT EXISTS RAW.AIRBYTE_INTERNAL COMMENT = 'Airbyte stages and state (Airbyte only)';

-- The owner of a schema can create, change and drop everything inside it.
-- COPY CURRENT GRANTS keeps any grant already given on the schema.
GRANT OWNERSHIP ON SCHEMA RAW.ECOMMERCE        TO ROLE LOADER COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA RAW.CRM              TO ROLE LOADER COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA RAW.ERP              TO ROLE LOADER COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA RAW.AIRBYTE_INTERNAL TO ROLE LOADER COPY CURRENT GRANTS;

-- USAGE on the database = permission to see and enter it.
-- CREATE SCHEMA: Airbyte runs "CREATE SCHEMA IF NOT EXISTS" before loading.
GRANT USAGE         ON DATABASE RAW TO ROLE LOADER;
GRANT CREATE SCHEMA ON DATABASE RAW TO ROLE LOADER;

-- Grants for TRANSFORMER, TRANSFORMER_PROD and ANALYST on RAW and ANALYTICS
-- are added in Stage 4 (dbt) and Stage 5 (governance).

SHOW SCHEMAS IN DATABASE RAW;
