output "resource_group_name" {
  description = "Resource group containing the Foundry resources."
  value       = azurerm_resource_group.main.name
}

output "foundry_account_name" {
  description = "Azure AI Foundry AIServices account name."
  value       = azurerm_cognitive_account.foundry.name
}

output "foundry_account_id" {
  description = "Azure resource ID of the Foundry AIServices account."
  value       = azurerm_cognitive_account.foundry.id
}

output "foundry_project_name" {
  description = "Foundry project resource name."
  value       = azapi_resource.foundry_project.name
}

output "foundry_project_id" {
  description = "Azure resource ID of the Foundry project."
  value       = azapi_resource.foundry_project.id
}

output "model_deployment_name" {
  description = "Model deployment name, when enabled."
  value       = var.deploy_model ? azurerm_cognitive_deployment.model[0].name : null
}

output "application_insights_connection_string" {
  description = "Application Insights connection string for agent telemetry."
  value       = azurerm_application_insights.main.connection_string
  sensitive   = true
}

output "mcp_acr_name" {
  description = "Azure Container Registry name for the MCP server image."
  value       = azurerm_container_registry.mcp.name
}

output "mcp_acr_login_server" {
  description = "Azure Container Registry login server for the MCP server image."
  value       = azurerm_container_registry.mcp.login_server
}

output "mcp_container_app_name" {
  description = "Container App name for the Coffee MCP server."
  value       = azurerm_container_app.mcp.name
}

output "mcp_server_url" {
  description = "Base URL for the Coffee MCP server."
  value       = "https://${azurerm_container_app.mcp.latest_revision_fqdn}"
}

output "mcp_sse_url" {
  description = "SSE endpoint URL for the Coffee MCP server."
  value       = "https://${azurerm_container_app.mcp.latest_revision_fqdn}/sse"
}

output "mcp_streamable_http_url" {
  description = "Streamable HTTP endpoint URL for the Coffee MCP server."
  value       = "https://${azurerm_container_app.mcp.latest_revision_fqdn}/mcp"
}
