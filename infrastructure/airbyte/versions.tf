# Terraform and provider versions.
# Terraform itself runs from the official Docker image pinned in tf.sh.
# The exact provider build is recorded in .terraform.lock.hcl (committed, like uv.lock).

terraform {
  required_version = "~> 1.17"

  required_providers {
    airbyte = {
      source  = "airbytehq/airbyte"
      version = "1.3.3"
    }
  }
}

# The provider is a client of the Airbyte public API (http://localhost:8000).
# Credentials: the API application created by abctl (`make airbyte-credentials`).
provider "airbyte" {
  server_url = "http://localhost:${var.airbyte_port}/api/public/v1/"
  # Required for a self-managed Airbyte: without it, the provider asks for the
  # token at a path that the local server answers with the web UI (HTML).
  token_url     = "http://localhost:${var.airbyte_port}/api/public/v1/applications/token"
  client_id     = var.airbyte_client_id
  client_secret = var.airbyte_client_secret
}
