import os

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


# RPAVS-56. First contractor handbook, shipped with the app. HR publishes later
# versions from the desk (new Handbook record, marked Active).
HANDBOOK_PDF = "data/RPA_Virtual_Staffing_Handbook.pdf"
DEFAULT_HANDBOOK = {
    "title": "RPA Virtual Staffing Contractor Handbook",
    "version": "2026",
}
# The RPA companies have their own handbook; their employees do not see this one.
HANDBOOK_EXCLUDED_COMPANIES = (
    "Real Property Associates Property Management",
    "Real Property Funding Group",
    "RPA Maintenance",
    "RPA Brokerage",
    "RPA Virtual Staffing",
)


def ensure_roles():
    for role_name, props in ROLES.items():
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc({"doctype": "Role", "role_name": role_name, **props}).insert(
                ignore_permissions=True
            )


def after_install():
    ensure_experience_levels()
    ensure_hiring_request_recipients()
    ensure_handbook()


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


def ensure_handbook():
    """Create the first Handbook from the bundled PDF. Runs once (install or the v0_3 patch)."""
    if frappe.db.count("Handbook"):
        return

    file_name = HANDBOOK_PDF.rsplit("/", 1)[-1]
    # Not get_app_path(app, HANDBOOK_PDF): it lowercases the path and the file name.
    with open(os.path.join(frappe.get_app_path("rpavs_platform"), HANDBOOK_PDF), "rb") as f:
        file_doc = frappe.get_doc(
            {"doctype": "File", "file_name": file_name, "is_private": 1, "content": f.read()}
        ).insert(ignore_permissions=True)

    handbook = frappe.get_doc(
        {
            "doctype": "Handbook",
            **DEFAULT_HANDBOOK,
            "is_active": 1,
            "file": file_doc.file_url,
            "excluded_companies": [
                {"company": company}
                for company in HANDBOOK_EXCLUDED_COMPANIES
                # Test and fresh sites do not have the RPA companies.
                if frappe.db.exists("Company", company)
            ],
        }
    ).insert(ignore_permissions=True)

    file_doc.db_set({"attached_to_doctype": "Handbook", "attached_to_name": handbook.name})
