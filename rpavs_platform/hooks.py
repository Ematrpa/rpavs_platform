app_name = "rpavs_platform"
app_title = "RPAVS Platform"
app_publisher = "RPA"
app_description = "RPAVS platform features backed by ERPNext (feedback and future portal integrations)"
app_email = "emanuel@rpapm.com"
app_license = "MIT"

required_apps = ["erpnext"]

# Roles must exist before the DocType permissions that reference them are synced.
before_install = "rpavs_platform.install.ensure_roles"
after_migrate = "rpavs_platform.install.ensure_roles"
