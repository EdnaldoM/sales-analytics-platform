# Values come from .env, passed by tf.sh as TF_VAR_<name> environment variables.
# "sensitive" hides a value in plan and apply output (it is still stored in the
# state file, which is why terraform.tfstate is git-ignored).

variable "airbyte_port" {
  description = "Port of the local Airbyte web UI and API"
  type        = number
  default     = 8000
}

variable "airbyte_workspace_id" {
  description = "Airbyte workspace UUID (from the web UI URL: /workspaces/<id>/...)"
  type        = string
}

variable "airbyte_client_id" {
  description = "Airbyte API client id"
  type        = string
  sensitive   = true
}

variable "airbyte_client_secret" {
  description = "Airbyte API client secret"
  type        = string
  sensitive   = true
}

variable "postgres_host" {
  description = "PostgreSQL host name as seen from Airbyte (Makefile: AIRBYTE_PG_HOST)"
  type        = string
  default     = "sources-postgres"
}

variable "airbyte_reader_password" {
  description = "Password of the read-only PostgreSQL role airbyte_reader"
  type        = string
  sensitive   = true
}

variable "snowflake_account" {
  description = "Snowflake account identifier, <orgname>-<accountname>"
  type        = string
}

variable "snowflake_private_key" {
  description = "Content of the AIRBYTE_SVC private key (PKCS#8 PEM)"
  type        = string
  sensitive   = true
}
