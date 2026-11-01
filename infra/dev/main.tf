// main.cf
terraform {
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "3.10.0"
    }
  }

//  backend "azurerm" {
//    use_cli = true
//    use_azuread_auth = true
//    tenant_id = "f8edff44-22a3-4b56-952d-e7012e1a6a0a"
//    storage_account_name = "ivartjterraformadventure"
//    container_name = "terraform"
//    key = "terraform.tfstate"
//  }
}

provider "azuread" {
  tenant_id = var.tenant_id
}

resource "azuread_application_registration" "applications" {
  for_each = var.applications
  display_name = each.value
}

resource "azuread_service_principal" "service_principals" {
  for_each = var.applications
  client_id = azuread_application_registration.applications[each.value].client_id
}

resource "azuread_group" "groups" {
  for_each = toset([for group in var.groups : group.name])
  display_name = each.value
  mail_enabled = false
  security_enabled = true
}

resource "azuread_group_member" "member_service_principals" {
  for_each = {
    for membership in flatten([
      for group in var.groups : [
        for member in group.members :
        {
          group_name = group.name
          member_name = member.name
        }
        if member.type == "application"
      ]
    ]):
    jsonencode([membership.group_name, membership.member_name]) => membership
  }
  group_object_id = azuread_group.groups[each.value.group_name].object_id
  member_object_id = azuread_service_principal.service_principals[each.value.member_name].object_id
}


resource "azuread_group_member" "member_groups" {
  for_each = {
    for membership in flatten([
      for group in var.groups : [
        for member in group.members :
        {
          group_name = group.name
          member_name = member.name
        }
        if member.type == "group"
      ]
    ]):
    jsonencode([membership.group_name, membership.member_name]) => membership
  }
  group_object_id = azuread_group.groups[each.value.group_name].object_id
  member_object_id = azuread_group.groups[each.value.member_name].object_id
}

