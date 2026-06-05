resource "random_string" "suffix" {
  length  = 6
  lower   = true
  numeric = true
  special = false
  upper   = false
}

locals {
  normalized_project_name = lower(replace(var.project_name, "_", "-"))
  compact_project_name    = substr(replace(local.normalized_project_name, "-", ""), 0, 12)

  resource_group_name  = var.resource_group_name != null && trimspace(var.resource_group_name) != "" ? var.resource_group_name : "rg-${local.normalized_project_name}"
  foundry_account_name = var.foundry_account_name != null && trimspace(var.foundry_account_name) != "" ? var.foundry_account_name : "aif-${local.normalized_project_name}-${random_string.suffix.result}"
  foundry_project_name = var.foundry_project_name != null && trimspace(var.foundry_project_name) != "" ? var.foundry_project_name : var.project_name
  log_analytics_name   = "log-${local.normalized_project_name}-${random_string.suffix.result}"
  app_insights_name    = "appi-${local.normalized_project_name}-${random_string.suffix.result}"
  acr_name             = "acr${local.compact_project_name}${random_string.suffix.result}"
  mcp_environment_name = "cae-${local.normalized_project_name}-mcp-${random_string.suffix.result}"
  mcp_identity_name    = "id-${local.normalized_project_name}-mcp-pull"
  mcp_app_name         = "ca-${local.normalized_project_name}-mcp"
}

resource "azurerm_resource_group" "main" {
  name     = local.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = local.log_analytics_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "main" {
  name                = local.app_insights_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = var.tags
}

resource "azurerm_cognitive_account" "foundry" {
  name                          = local.foundry_account_name
  location                      = azurerm_resource_group.main.location
  resource_group_name           = azurerm_resource_group.main.name
  kind                          = "AIServices"
  sku_name                      = var.foundry_sku_name
  custom_subdomain_name         = local.foundry_account_name
  local_auth_enabled            = var.local_auth_enabled
  project_management_enabled    = true
  public_network_access_enabled = true
  tags                          = var.tags

  identity {
    type = "SystemAssigned"
  }
}

resource "azapi_resource" "foundry_project" {
  type                      = "Microsoft.CognitiveServices/accounts/projects@2025-06-01"
  name                      = local.foundry_project_name
  parent_id                 = azurerm_cognitive_account.foundry.id
  location                  = azurerm_resource_group.main.location
  schema_validation_enabled = false

  body = {
    sku = {
      name = var.foundry_sku_name
    }
    identity = {
      type = "SystemAssigned"
    }
    properties = {
      displayName = var.project_name
      description = "Azure AI Foundry project for ${var.project_name} agents."
    }
  }
}

resource "azurerm_cognitive_deployment" "model" {
  count = var.deploy_model ? 1 : 0

  name                 = var.model_deployment_name
  cognitive_account_id = azurerm_cognitive_account.foundry.id

  sku {
    name     = var.model_sku_name
    capacity = var.model_capacity
  }

  model {
    format  = "OpenAI"
    name    = var.model_name
    version = var.model_version
  }
}

resource "azurerm_container_registry" "mcp" {
  name                = local.acr_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_container_app_environment" "mcp" {
  name                       = local.mcp_environment_name
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  tags                       = var.tags
}

resource "azurerm_user_assigned_identity" "mcp_pull" {
  name                = local.mcp_identity_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  tags                = var.tags
}

resource "azurerm_role_assignment" "mcp_acr_pull" {
  scope                = azurerm_container_registry.mcp.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.mcp_pull.principal_id
}

resource "azurerm_container_app" "mcp" {
  name                         = local.mcp_app_name
  container_app_environment_id = azurerm_container_app_environment.mcp.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.mcp_pull.id]
  }

  registry {
    server   = azurerm_container_registry.mcp.login_server
    identity = azurerm_user_assigned_identity.mcp_pull.id
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "coffee-mcp-server"
      image  = "${azurerm_container_registry.mcp.login_server}/${var.mcp_image_repository}:${var.mcp_image_tag}"
      cpu    = var.mcp_container_cpu
      memory = var.mcp_container_memory

      env {
        name  = "HOST"
        value = "0.0.0.0"
      }

      env {
        name  = "PORT"
        value = "8000"
      }

      env {
        name  = "MCP_TRANSPORT"
        value = "sse"
      }
    }
  }

  depends_on = [azurerm_role_assignment.mcp_acr_pull]
}
