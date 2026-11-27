-- =============================================================================
-- 01 · Resource monitor: monthly credit cap for the whole account
-- Run as: ACCOUNTADMIN (only this role can create account-level monitors)
-- Idempotent: safe to run again; it re-applies the same settings.
-- Docs: https://docs.snowflake.com/en/user-guide/resource-monitors
-- =============================================================================

USE ROLE ACCOUNTADMIN;

-- Creates the monitor only if it does not exist yet. "CREATE OR REPLACE" is
-- avoided on purpose: it would drop the monitor and detach it from the account.
-- The monthly cycle starts when the monitor is created and is not reset on reruns.
CREATE RESOURCE MONITOR IF NOT EXISTS ACCOUNT_MONTHLY_CAP WITH
    FREQUENCY = MONTHLY
    START_TIMESTAMP = IMMEDIATELY;

-- Quota and actions are applied with ALTER, so a change here takes effect on every run.
-- 1 credit = 1 hour of an X-Small warehouse. A sync or a dbt build of this
-- project takes minutes, so 20 credits per month is a generous cap.
ALTER RESOURCE MONITOR ACCOUNT_MONTHLY_CAP SET
    CREDIT_QUOTA = 20
    TRIGGERS
        ON 50 PERCENT DO NOTIFY             -- email to account administrators
        ON 75 PERCENT DO NOTIFY
        ON 100 PERCENT DO SUSPEND           -- running queries finish, no new ones start
        ON 110 PERCENT DO SUSPEND_IMMEDIATE; -- running queries are cancelled

-- Applies the monitor to every warehouse in the account.
ALTER ACCOUNT SET RESOURCE_MONITOR = ACCOUNT_MONTHLY_CAP;

SHOW RESOURCE MONITORS LIKE 'ACCOUNT_MONTHLY_CAP';
