# Ingestion: 3 PostgreSQL sources -> 1 Snowflake destination -> 3 connections.
# Design: docs/decisions/0006-cursor-based-incremental-ingestion.md
#
# The generic airbyte_source / airbyte_destination resources take the connector
# configuration as JSON. The airbyte_connector_configuration data source builds
# that JSON and validates it against the connector's spec during `plan`.
# Connector versions match the ones the local Airbyte runs (Stage 3 validation).

locals {
  # One source and one connection per database. Every table is synced with:
  # cursor = updated_at (maintained by a trigger), primary key = the table's PK.
  databases = {
    ecommerce = {
      customers    = "customer_id"
      orders       = "order_id"
      order_items  = "order_item_id"
      payments     = "payment_id"
      returns      = "return_id"
      return_items = "return_item_id"
    }
    crm = {
      customers         = "crm_customer_id"
      customer_contacts = "contact_id"
    }
    erp = {
      product_categories   = "category_id"
      products             = "product_id"
      product_cost_history = "cost_id"
    }
  }
}

# -----------------------------------------------------------------------------
# Sources: one per PostgreSQL database
# -----------------------------------------------------------------------------
data "airbyte_connector_configuration" "postgres" {
  for_each = local.databases

  connector_name     = "source-postgres"
  connector_version  = "3.8.13"
  connector_registry = "oss"

  configuration = {
    host               = var.postgres_host
    port               = 5432
    database           = each.key
    schemas            = ["public"]
    username           = "airbyte_reader"
    ssl_mode           = { mode = "disable" } # local network only
    tunnel_method      = { tunnel_method = "NO_TUNNEL" }
    replication_method = { method = "Standard" } # cursor-based (ADR-0006), not CDC or xmin
  }

  configuration_secrets = {
    password = var.airbyte_reader_password
  }
}

resource "airbyte_source" "postgres" {
  for_each = local.databases

  name          = "postgres-${each.key}"
  workspace_id  = var.airbyte_workspace_id
  definition_id = data.airbyte_connector_configuration.postgres[each.key].definition_id
  configuration = data.airbyte_connector_configuration.postgres[each.key].configuration_json
}

# -----------------------------------------------------------------------------
# Destination: Snowflake RAW database (infrastructure/snowflake/)
# -----------------------------------------------------------------------------
data "airbyte_connector_configuration" "snowflake" {
  connector_name     = "destination-snowflake"
  connector_version  = "5.2.3"
  connector_registry = "oss"

  configuration = {
    host      = "${var.snowflake_account}.snowflakecomputing.com"
    role      = "LOADER"
    warehouse = "INGEST_WH"
    database  = "RAW"
    username  = "AIRBYTE_SVC"

    # Default schema, used only by the connection check: every connection
    # writes to its own schema (namespace_format below).
    schema = "AIRBYTE_INTERNAL"

    # Airbyte's internal schema. The default is "airbyte_internal": a second,
    # lowercase schema next to the one created by 04_databases.sql.
    raw_data_schema = "AIRBYTE_INTERNAL"

    # The default (FLOAT) stores decimals approximately. Money must be exact.
    number_data_type = "NUMBER(38,9)"

    # The default (true) trims leading and trailing spaces from text. Bronze must
    # keep source values as they are: the spaces are planned quality issues (Q1, Q6).
    trim_space = false

    # Typed final tables (Direct Load), no legacy raw tables.
    disable_type_dedupe = false
  }

  configuration_secrets = {
    credentials = {
      auth_type   = "Key Pair Authentication"
      private_key = var.snowflake_private_key
    }
  }
}

resource "airbyte_destination" "snowflake" {
  name          = "snowflake-raw"
  workspace_id  = var.airbyte_workspace_id
  definition_id = data.airbyte_connector_configuration.snowflake.definition_id
  configuration = data.airbyte_connector_configuration.snowflake.configuration_json
}

# -----------------------------------------------------------------------------
# Connections: one per database, written to RAW.<DATABASE>
# -----------------------------------------------------------------------------
resource "airbyte_connection" "postgres_to_snowflake" {
  for_each = local.databases

  name           = "${each.key} -> snowflake"
  source_id      = airbyte_source.postgres[each.key].source_id
  destination_id = airbyte_destination.snowflake.destination_id
  status         = "active"

  namespace_definition = "custom_format"
  namespace_format     = upper(each.key) # RAW.ECOMMERCE, RAW.CRM, RAW.ERP

  # Manual until Stage 6: Airflow triggers the syncs.
  schedule = {
    schedule_type = "manual"
    # Unused by a manual schedule, but must be set: provider 1.3.3 copies this
    # value from the configuration instead of the API response, and leaving it
    # out fails the apply with "unknown value ... cron_time_zone".
    cron_time_zone = "UTC"
  }

  # New source columns are added to the destination automatically; breaking
  # changes (removed or retyped columns) stop the connection for review.
  non_breaking_schema_updates_behavior = "propagate_columns"

  configurations = {
    streams = [
      for table, primary_key in each.value : {
        name = table
        # Incremental | Append + Deduped: one row per primary key in RAW, the
        # latest version by cursor. Re-read rows (cursor ties) replace themselves.
        sync_mode    = "incremental_deduped_history"
        cursor_field = ["updated_at"]
        primary_key  = [[primary_key]]
      }
    ]
  }
}
