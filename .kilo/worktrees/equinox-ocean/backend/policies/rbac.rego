package jurislab.rbac

import data.jurislab.roles

default allow := false
default reason := "denied_by_policy"

# Platform-admin-level access
allow if {
    member("platform_admin", input.user.platform_roles)
}

# Organization-admin-level access
allow if {
    member("org_admin", input.user.platform_roles)
}

# Generic module permission request
# input: { user: { platform_roles, module_roles }, resource: { module, permission } }
allow if {
    input.action == "module"
    permitted(input.resource.module, input.resource.permission, input.user.module_roles)
}

reason := "missing_module_permission" if {
    input.action == "module"
    not is_admin(input.user.platform_roles)
    not permitted(input.resource.module, input.resource.permission, input.user.module_roles)
}