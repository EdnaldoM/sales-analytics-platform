# Connection ids: needed to trigger syncs from Airflow (Stage 6).
# Show them with: make airbyte-plan (after an apply) or tf.sh output
output "connection_ids" {
  description = "Airbyte connection id per source database"
  value       = { for db, connection in airbyte_connection.postgres_to_snowflake : db => connection.connection_id }
}
