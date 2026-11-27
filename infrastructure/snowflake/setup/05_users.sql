-- =============================================================================
-- 05 · Service users
-- Run as: USERADMIN
-- Idempotent: safe to run again.
-- Design: docs/governance/data-governance.md (section 2.1)
-- Docs: https://docs.snowflake.com/en/user-guide/key-pair-auth
--
-- TYPE = SERVICE: a user for programs. It cannot log in with a password or use
-- the web interface; it authenticates with a key pair. The private key stays on
-- the machine that runs the program; Snowflake stores only the public key.
--
-- dbt users (DBT_CI_SVC, DBT_PROD_SVC) are added in Stages 4 and 7,
-- ANALYST_DEMO in Stage 5.
-- =============================================================================

USE ROLE USERADMIN;

CREATE USER IF NOT EXISTS AIRBYTE_SVC TYPE = SERVICE;

ALTER USER AIRBYTE_SVC SET
    TYPE = SERVICE
    DEFAULT_ROLE = LOADER
    DEFAULT_WAREHOUSE = INGEST_WH
    COMMENT = 'Airbyte Snowflake destination';

GRANT ROLE LOADER TO USER AIRBYTE_SVC;

-- -----------------------------------------------------------------------------
-- Public key: done once per key, NOT part of the script run.
-- 1. Generate the key pair (infrastructure/snowflake/README.md, step 2).
-- 2. In the worksheet, uncomment the statement below and paste the content of
--    airbyte_svc.pub between the quotes: one line, without the
--    "-----BEGIN PUBLIC KEY-----" and "-----END PUBLIC KEY-----" lines.
-- 3. Run only that statement. Do not save the key in this file.
-- -----------------------------------------------------------------------------
-- ALTER USER AIRBYTE_SVC SET RSA_PUBLIC_KEY = 'MIIBIjANBgkqh...';

-- RSA_PUBLIC_KEY_FP shows a fingerprint once a key is set.
DESC USER AIRBYTE_SVC;
