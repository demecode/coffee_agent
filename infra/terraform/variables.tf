variable "subscription_id" {
  description = "Azure subscription ID used for the Foundry deployment."
  type        = string
}

variable "location" {
  description = "Azure region for the resource group and Foundry resources."
  type        = string
  default     = "uksouth"
}

variable "project_name" {
  description = "Foundry project display name and default project resource name."
  type        = string
  default     = "coffee-agent"

  validation {
    condition     = can(regex("^[a-zA-Z0-9_-]{2,40}$", var.project_name))
    error_message = "project_name must be 2-40 characters and contain only letters, numbers, hyphens, and underscores."
  }
}

variable "resource_group_name" {
  description = "Optional explicit resource group name. When unset, one is derived from project_name."
  type        = string
  default     = null

  validation {
    condition     = var.resource_group_name == null || can(regex("^[A-Za-z0-9._()\\-]{1,90}$", var.resource_group_name))
    error_message = "resource_group_name must be 1-90 characters and use Azure resource group safe characters."
  }
}

variable "foundry_account_name" {
  description = "Optional explicit Azure AI Foundry account name. Azure Cognitive Services account names cannot contain underscores."
  type        = string
  default     = null

  validation {
    condition     = var.foundry_account_name == null || can(regex("^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$", var.foundry_account_name))
    error_message = "foundry_account_name must be 3-64 lowercase letters, numbers, or hyphens, start/end with a letter or number, and cannot contain underscores."
  }
}

variable "foundry_project_name" {
  description = "Optional explicit Foundry project resource name. When unset, project_name is used."
  type        = string
  default     = null

  validation {
    condition     = var.foundry_project_name == null || can(regex("^[A-Za-z0-9_-]{2,40}$", var.foundry_project_name))
    error_message = "foundry_project_name must be 2-40 characters and contain only letters, numbers, hyphens, and underscores."
  }
}

variable "foundry_sku_name" {
  description = "SKU for the Foundry AIServices account."
  type        = string
  default     = "S0"
}

variable "local_auth_enabled" {
  description = "Whether to allow API-key authentication for the Foundry account."
  type        = bool
  default     = false
}

variable "deploy_model" {
  description = "Whether to create a sample model deployment for agents."
  type        = bool
  default     = true
}

variable "model_deployment_name" {
  description = "Name of the Azure OpenAI model deployment."
  type        = string
  default     = "gpt-4o"
}

variable "model_name" {
  description = "Model name to deploy."
  type        = string
  default     = "gpt-4o"
}

variable "model_version" {
  description = "Model version to deploy."
  type        = string
  default     = "2024-11-20"
}

variable "model_sku_name" {
  description = "Model deployment SKU. Common values include GlobalStandard and Standard."
  type        = string
  default     = "GlobalStandard"
}

variable "model_capacity" {
  description = "Capacity for the model deployment."
  type        = number
  default     = 1
}

variable "mcp_image_repository" {
  description = "Container repository name for the Coffee MCP server image."
  type        = string
  default     = "coffee-mcp-server"
}

variable "mcp_image_tag" {
  description = "Container image tag for the Coffee MCP server."
  type        = string
  default     = "latest"
}

variable "mcp_container_cpu" {
  description = "CPU cores allocated to the MCP Container App."
  type        = number
  default     = 0.25
}

variable "mcp_container_memory" {
  description = "Memory allocated to the MCP Container App."
  type        = string
  default     = "0.5Gi"
}

variable "tags" {
  description = "Tags applied to Azure resources."
  type        = map(string)
  default = {
    application = "coffee-now"
    managed-by  = "terraform"
  }
}
