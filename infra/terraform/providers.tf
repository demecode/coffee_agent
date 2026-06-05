provider "azurerm" {
  subscription_id     = var.subscription_id
  storage_use_azuread = true

  features {
    resource_group {
      prevent_deletion_if_contains_resources = false
    }
  }
}

provider "azapi" {
  subscription_id = var.subscription_id
}
