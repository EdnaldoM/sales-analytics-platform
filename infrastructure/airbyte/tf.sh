#!/usr/bin/env bash
# Runs Terraform from its official Docker image, so nothing is installed on the
# machine. Usage (from the repository root; the Makefile wraps it):
#   infrastructure/airbyte/tf.sh init | plan | apply | output | destroy
#
# Values come from .env and are passed as TF_VAR_<name> environment variables,
# so secrets never appear on the command line or in versioned files.
set -euo pipefail

TERRAFORM_IMAGE="hashicorp/terraform:1.17.2"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="$ROOT/.env"
KEY_FILE="${SNOWFLAKE_AIRBYTE_KEY:-$HOME/.snowflake/keys/airbyte_svc.p8}"

[ -f "$ENV_FILE" ] || { echo "Missing .env. Run 'make setup'." >&2; exit 1; }
[ -f "$KEY_FILE" ] || { echo "Missing private key $KEY_FILE (infrastructure/snowflake/README.md, step 2)." >&2; exit 1; }

# Load .env into this shell only
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

for var in AIRBYTE_WORKSPACE_ID AIRBYTE_CLIENT_ID AIRBYTE_CLIENT_SECRET \
           AIRBYTE_READER_PASSWORD SNOWFLAKE_ACCOUNT; do
    [ -n "${!var:-}" ] || { echo "Set $var in .env" >&2; exit 1; }
done

export TF_VAR_airbyte_port="${AIRBYTE_PORT:-8000}"
export TF_VAR_airbyte_workspace_id="$AIRBYTE_WORKSPACE_ID"
export TF_VAR_airbyte_client_id="$AIRBYTE_CLIENT_ID"
export TF_VAR_airbyte_client_secret="$AIRBYTE_CLIENT_SECRET"
export TF_VAR_airbyte_reader_password="$AIRBYTE_READER_PASSWORD"
export TF_VAR_snowflake_account="$SNOWFLAKE_ACCOUNT"
TF_VAR_snowflake_private_key="$(cat "$KEY_FILE")"
export TF_VAR_snowflake_private_key

# --network host : the container reaches Airbyte at localhost:8000
# --user         : files created in the folder (.terraform, state) belong to you
# -e NAME        : passes the variable from this shell without writing its value here
# -t             : only when attached to a terminal (apply asks for "yes")
tty_flag=()
[ -t 0 ] && tty_flag=(-t)

exec docker run --rm -i "${tty_flag[@]}" \
    --network host \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -e CHECKPOINT_DISABLE=1 \
    -e TF_VAR_airbyte_port \
    -e TF_VAR_airbyte_workspace_id \
    -e TF_VAR_airbyte_client_id \
    -e TF_VAR_airbyte_client_secret \
    -e TF_VAR_airbyte_reader_password \
    -e TF_VAR_snowflake_account \
    -e TF_VAR_snowflake_private_key \
    -v "$ROOT/infrastructure/airbyte:/workspace" \
    -w /workspace \
    "$TERRAFORM_IMAGE" "$@"
