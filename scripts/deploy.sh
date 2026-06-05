#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform"
PLAN_FILE="${TF_DIR}/main.tfplan"

if [ -f "${ROOT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

PROJECT_NAME="${PROJECT_NAME:-coffee-agent}"
AZURE_LOCATION="${AZURE_LOCATION:-northcentralus}"
AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-$(az account show --query id -o tsv)}"
TF_STATE_RESOURCE_GROUP="${TF_STATE_RESOURCE_GROUP:-rg-coffee-agent-tfstate}"
TF_STATE_CONTAINER="${TF_STATE_CONTAINER:-tfstate}"
TF_STATE_KEY="${TF_STATE_KEY:-coffee-agent.tfstate}"
MCP_IMAGE_REPOSITORY="${TF_VAR_mcp_image_repository:-coffee-mcp-server}"
MCP_IMAGE_TAG="${TF_VAR_mcp_image_tag:-latest}"
ACR_PLAN_FILE="${TF_DIR}/acr.tfplan"
MCP_BUILD_CONTEXT="${ROOT_DIR}/.mcp_build_context"

if [ -z "${TF_STATE_STORAGE_ACCOUNT:-}" ]; then
  STATE_HASH="$(printf "%s" "${AZURE_SUBSCRIPTION_ID}-${PROJECT_NAME}" | shasum -a 256 | awk '{print substr($1, 1, 16)}')"
  TF_STATE_STORAGE_ACCOUNT="tfst${STATE_HASH}"
fi

"${ROOT_DIR}/scripts/bootstrap_tf_state.sh"

export ARM_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID}"
export TF_VAR_subscription_id="${AZURE_SUBSCRIPTION_ID}"
export TF_VAR_location="${AZURE_LOCATION}"
export TF_VAR_project_name="${PROJECT_NAME}"

terraform -chdir="${TF_DIR}" init -upgrade \
  -backend-config="resource_group_name=${TF_STATE_RESOURCE_GROUP}" \
  -backend-config="storage_account_name=${TF_STATE_STORAGE_ACCOUNT}" \
  -backend-config="container_name=${TF_STATE_CONTAINER}" \
  -backend-config="key=${TF_STATE_KEY}" \
  -backend-config="use_azuread_auth=true"

terraform -chdir="${TF_DIR}" plan \
  -target=random_string.suffix \
  -target=azurerm_resource_group.main \
  -target=azurerm_container_registry.mcp \
  -out="${ACR_PLAN_FILE}"
terraform -chdir="${TF_DIR}" apply "${ACR_PLAN_FILE}"

MCP_ACR_NAME="$(terraform -chdir="${TF_DIR}" output -raw mcp_acr_name)"
mkdir -p "${MCP_BUILD_CONTEXT}"
rm -rf "${MCP_BUILD_CONTEXT}/mcp_server"
cp -R "${ROOT_DIR}/mcp_server" "${MCP_BUILD_CONTEXT}/mcp_server"

if [ "${MCP_IMAGE_TAG}" = "latest" ]; then
  MCP_IMAGE_HASH="$(find "${ROOT_DIR}/mcp_server" -type f -not -path '*/__pycache__/*' -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | awk '{print substr($1, 1, 12)}')"
  MCP_IMAGE_TAG="mcp-${MCP_IMAGE_HASH}"
fi

export TF_VAR_mcp_image_tag="${MCP_IMAGE_TAG}"
echo "Using MCP image tag: ${MCP_IMAGE_TAG}"

az acr build \
  --registry "${MCP_ACR_NAME}" \
  --resource-group "${TF_VAR_resource_group_name:-rg-${PROJECT_NAME//_/-}}" \
  --image "${MCP_IMAGE_REPOSITORY}:${MCP_IMAGE_TAG}" \
  --file "${MCP_BUILD_CONTEXT}/mcp_server/Dockerfile" \
  "${MCP_BUILD_CONTEXT}"

terraform -chdir="${TF_DIR}" plan -out="${PLAN_FILE}"
terraform -chdir="${TF_DIR}" apply "${PLAN_FILE}"
terraform -chdir="${TF_DIR}" output
