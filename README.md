# Coffee Agent

Dummy child repository for the `alpha` workspace.

## Run

```bash
python -m coffee_agent
```

## Test

```bash
python -m pytest
```

## Python environment

Create the local virtual environment and install the agent dependencies:

```bash
./scripts/setup_python_env.sh
source .venv/bin/activate
```

Required packages are pinned in `requirements.txt`.

## Azure AI Foundry infrastructure

Terraform lives in `infra/terraform` and uses an Azure Storage remote backend for state. The lifecycle scripts read `.env` when present and otherwise use safe defaults.

```bash
cp .env.example .env
# Edit .env if you want a different subscription, location, project name, or state backend.

./scripts/deploy.sh
./scripts/teardown.sh
./scripts/redeploy.sh
```

The deploy script:

- Creates the Terraform state resource group, storage account, and blob container if needed.
- Initializes Terraform with the Azure Blob backend.
- Creates a resource group, Azure AI Foundry `AIServices` account, Foundry project, Application Insights, and an optional model deployment for agents.

The teardown script destroys only resources managed by the Terraform state. It intentionally keeps the remote state storage account so state history is not lost accidentally.

Destroy and redeploy operations ask you to type the project name before applying the destroy plan. For automation, set `CONFIRM_DESTROY=<project-name>`.

### Switching Azure regions

Azure resource group locations are immutable. To move the Foundry resources to a different region, keep the Terraform state backend settings stable, update `AZURE_LOCATION`, then run:

```bash
./scripts/teardown.sh
./scripts/deploy.sh
```

For the current setup, the app resources are configured for `uksouth` and the existing Terraform state backend remains in `westeurope` under `rg-coffee-now-tfstate`.
