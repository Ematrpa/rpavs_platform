import frappe

# Client Admin / Client Supervisor already exist on erp.rpa-hub.com (they are the
# portal roles). They are only created here so a fresh site can install the app.
ROLES = {
    "Client Admin": {"desk_access": 0},
    "Client Supervisor": {"desk_access": 0},
    # Back office users who review feedback and receive the new-feedback email.
    "Feedback Reviewer": {"desk_access": 1},
}


def ensure_roles():
    for role_name, props in ROLES.items():
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name, **props}).insert(
                ignore_permissions=True
            )
