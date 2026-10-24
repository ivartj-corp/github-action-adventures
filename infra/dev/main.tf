variable "tenant_id" {
  type = string
  nullable = false
}

variable "applications" {
  type = set(string)
  nullable = false
  default = []
}

variable "groups" {
  type = set(
    object({
      name = string
      members = set(
        object({
          type = string
          name = string
        })
      )
    })
  )
  nullable = false
  default = []

  validation {
    condition = alltrue(
      flatten([
        for group in var.groups : [
          for member in group.members :
          contains(["group", "application"], member.type)
        ]
      ])
    )
    error_message = "member type must be either 'group' or 'application'"
  }

  validation {
    condition = alltrue(
      flatten([
        for group in var.groups : [
          for member in group.members :
          contains(var.applications, member.name)
          if member.type == "application"
        ]
      ])
    )
    error_message = "members of type 'application' must passed in the 'applications' variable"
  }

  validation {
    condition = alltrue(
      flatten([
        for group in var.groups : [
          for member in group.members :
          contains([for group in var.groups : group.name], member.name)
          if member.type == "group"
        ]
      ])
    )
    error_message = "members of type 'group' must passed in the 'groups' variable"
  }
}

// main.cf
terraform {
  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "3.10.0"
    }
  }
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

