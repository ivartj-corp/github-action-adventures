tenant_id = "f8edff44-22a3-4b56-952d-e7012e1a6a0a"
applications = ["foo-app", "bar-app"]
groups = [
  {
    name = "foo-group"
    members = [
      {
        type = "application"
        name = "foo-app"
      }
    ]
  },
  {
    name = "bar-group"
    members = [
      {
        type = "group"
        name = "foo-group"
      }
    ]
  }
]
