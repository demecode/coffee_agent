#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "${ROOT_DIR}/requirements.txt"

python - <<'PY'
import importlib.metadata as metadata

packages = [
    "azure-ai-projects",
    "azure-identity",
    "python-dotenv",
    "openai",
    "jsonref",
    "pytest",
]

for package in packages:
    print(f"{package}=={metadata.version(package)}")
PY
