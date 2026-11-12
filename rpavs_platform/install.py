import frappe

ROLES = {
    # Back office users who review feedback and receive the new-feedback email.
    "Feedback Reviewer": {"desk_access": 1},
}


def ensure_roles():
    for role_name, props in ROLES.items():
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name, **props}).insert(
                ignore_permissions=True
            )
