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
    error_message = "members of type 'application' must be passed in the 'applications' variable"
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
    error_message = "members of type 'group' must be passed in the 'groups' variable"
  }
}

