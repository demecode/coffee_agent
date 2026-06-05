#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform"
PLAN_FILE="${TF_DIR}/main.destroy.tfplan"

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

if [ -z "${TF_STATE_STORAGE_ACCOUNT:-}" ]; then
  STATE_HASH="$(printf "%s" "${AZURE_SUBSCRIPTION_ID}-${PROJECT_NAME}" | shasum -a 256 | awk '{print substr($1, 1, 16)}')"
  TF_STATE_STORAGE_ACCOUNT="tfst${STATE_HASH}"
fi

if [ "${CONFIRM_DESTROY:-}" != "${PROJECT_NAME}" ]; then
  read -r -p "Destroy Terraform-managed Azure resources for '${PROJECT_NAME}'? Type '${PROJECT_NAME}' to continue: " CONFIRM_DESTROY
  if [ "${CONFIRM_DESTROY}" != "${PROJECT_NAME}" ]; then
    echo "Teardown cancelled."
    exit 1
  fi
fi

export ARM_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID}"
export TF_VAR_subscription_id="${AZURE_SUBSCRIPTION_ID}"
export TF_VAR_location="${AZURE_LOCATION}"
export TF_VAR_project_name="${PROJECT_NAME}"

terraform -chdir="${TF_DIR}" init \
  -backend-config="resource_group_name=${TF_STATE_RESOURCE_GROUP}" \
  -backend-config="storage_account_name=${TF_STATE_STORAGE_ACCOUNT}" \
  -backend-config="container_name=${TF_STATE_CONTAINER}" \
  -backend-config="key=${TF_STATE_KEY}" \
  -backend-config="use_azuread_auth=true"

terraform -chdir="${TF_DIR}" plan -destroy -out="${PLAN_FILE}"
terraform -chdir="${TF_DIR}" apply "${PLAN_FILE}"

echo "Azure resources managed by this Terraform state were destroyed."
echo "Terraform state storage was intentionally retained in ${TF_STATE_RESOURCE_GROUP}/${TF_STATE_STORAGE_ACCOUNT}."
