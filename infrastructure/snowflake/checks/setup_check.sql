-- =============================================================================
-- Setup check: confirms that the scripts in setup/ were applied.
-- Run as: ACCOUNTADMIN (read-only statements)
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Expected: ACCOUNT_MONTHLY_CAP, credit_quota 20, level ACCOUNT
SHOW RESOURCE MONITORS;

-- Expected: INGEST_WH, TRANSFORM_WH, REPORTING_WH · X-Small · auto_suspend 60 · suspended
SHOW WAREHOUSES;

-- Expected: AIRBYTE_INTERNAL, CRM, ECOMMERCE, ERP owned by LOADER
SHOW SCHEMAS IN DATABASE RAW;

-- Expected: USAGE on INGEST_WH, USAGE + CREATE SCHEMA on RAW, OWNERSHIP of the 4 schemas
SHOW GRANTS TO ROLE LOADER;

-- Expected: role LOADER
SHOW GRANTS TO USER AIRBYTE_SVC;

-- Expected: type SERVICE, default_role LOADER, has_rsa_public_key true
SHOW USERS LIKE 'AIRBYTE_SVC';
