#!/usr/bin/env bash
# Runs once, on first start with an empty data volume (official image behavior).
# Creates the application roles and the three source databases.
#
# Passwords come from environment variables and are passed to psql as
# variables (:'name'), so special characters are quoted safely.
set -Eeo pipefail

: "${GENERATOR_PASSWORD:?GENERATOR_PASSWORD is not set}"
: "${AIRBYTE_READER_PASSWORD:?AIRBYTE_READER_PASSWORD is not set}"

psql -v ON_ERROR_STOP=1 \
    --username "$POSTGRES_USER" \
    --dbname postgres \
    -v generator_password="$GENERATOR_PASSWORD" \
    -v airbyte_reader_password="$AIRBYTE_READER_PASSWORD" <<-'EOSQL'
	-- generator: owns the source databases and writes all data
	CREATE ROLE generator WITH LOGIN PASSWORD :'generator_password';

	-- airbyte_reader: read-only account for ingestion (Stage 3)
	CREATE ROLE airbyte_reader WITH LOGIN PASSWORD :'airbyte_reader_password';

	CREATE DATABASE ecommerce OWNER generator;
	CREATE DATABASE crm       OWNER generator;
	CREATE DATABASE erp       OWNER generator;
EOSQL
