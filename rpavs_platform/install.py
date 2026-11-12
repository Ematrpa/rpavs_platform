import frappe

ROLES = {
    # Back office users who review feedback and receive the new-feedback email.
    "Feedback Reviewer": {"desk_access": 1},
    # RPAVS-44. Both already exist on production; created here only for new or test
    # sites, so the Hiring Request permissions have roles to point at.
    "Recruiter": {"desk_access": 1},
    "Client Admin": {"desk_access": 0},
}

# RPAVS-44 starting values. Recruiters add, rename or disable levels from the desk,
# so these are only inserted while the table is empty.
DEFAULT_EXPERIENCE_LEVELS = ("Junior", "Mid", "Senior")

# First recipient of the new-hiring-request email. Recruiting edits the list in
# Hiring Request Settings; this runs once (install or the v0_2 patch), never on migrate.
DEFAULT_HIRING_REQUEST_RECIPIENTS = ("scortez@rpapm.com",)


def ensure_roles():
    for role_name, props in ROLES.items():
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name, **props}).insert(
                ignore_permissions=True
            )


def after_install():
    ensure_experience_levels()
    ensure_hiring_request_recipients()


def after_migrate():
    ensure_roles()
    ensure_experience_levels()


def ensure_experience_levels():
    if frappe.db.count("Hiring Experience Level"):
        return
    for order, level in enumerate(DEFAULT_EXPERIENCE_LEVELS):
        frappe.get_doc(
            {
                "doctype": "Hiring Experience Level",
                "level_name": level,
                "enabled": 1,
                "display_order": order,
            }
        ).insert(ignore_permissions=True)


def ensure_hiring_request_recipients():
    settings = frappe.get_single("Hiring Request Settings")
    if settings.notify_recipients:
        return
    for email in DEFAULT_HIRING_REQUEST_RECIPIENTS:
        settings.append("notify_recipients", {"email": email, "enabled": 1})
    settings.save(ignore_permissions=True)
