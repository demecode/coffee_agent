#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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
TF_STATE_LOCATION="${TF_STATE_LOCATION:-${AZURE_LOCATION}}"
TF_STATE_CONTAINER="${TF_STATE_CONTAINER:-tfstate}"

if [ -z "${TF_STATE_STORAGE_ACCOUNT:-}" ]; then
  STATE_HASH="$(printf "%s" "${AZURE_SUBSCRIPTION_ID}-${PROJECT_NAME}" | shasum -a 256 | awk '{print substr($1, 1, 16)}')"
  TF_STATE_STORAGE_ACCOUNT="tfst${STATE_HASH}"
fi

az account set --subscription "${AZURE_SUBSCRIPTION_ID}"

az group create \
  --name "${TF_STATE_RESOURCE_GROUP}" \
  --location "${TF_STATE_LOCATION}" \
  --tags application="${PROJECT_NAME}" managed-by="terraform" purpose="tfstate" \
  --output none

az storage account create \
  --name "${TF_STATE_STORAGE_ACCOUNT}" \
  --resource-group "${TF_STATE_RESOURCE_GROUP}" \
  --location "${TF_STATE_LOCATION}" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --allow-blob-public-access false \
  --https-only true \
  --tags application="${PROJECT_NAME}" managed-by="terraform" purpose="tfstate" \
  --output none

SIGNED_IN_USER_ID="$(az ad signed-in-user show --query id -o tsv 2>/dev/null || true)"
STORAGE_ACCOUNT_ID="$(az storage account show --name "${TF_STATE_STORAGE_ACCOUNT}" --resource-group "${TF_STATE_RESOURCE_GROUP}" --query id -o tsv)"

if [ -n "${SIGNED_IN_USER_ID}" ]; then
  az role assignment create \
    --assignee "${SIGNED_IN_USER_ID}" \
    --role "Storage Blob Data Contributor" \
    --scope "${STORAGE_ACCOUNT_ID}" \
    --output none 2>/dev/null || true
fi

az storage container create \
  --name "${TF_STATE_CONTAINER}" \
  --account-name "${TF_STATE_STORAGE_ACCOUNT}" \
  --auth-mode login \
  --output none

cat <<EOF
Terraform state backend is ready:
  resource_group_name  = ${TF_STATE_RESOURCE_GROUP}
  location             = ${TF_STATE_LOCATION}
  storage_account_name = ${TF_STATE_STORAGE_ACCOUNT}
  container_name       = ${TF_STATE_CONTAINER}
EOF
