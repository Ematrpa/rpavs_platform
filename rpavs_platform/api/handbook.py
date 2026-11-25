"""
Contractor handbook (RPAVS-56). The RPAVS platform shows the active Handbook page by
page and calls these methods with the employee's own session. Every rule is enforced
here, not in the client:

- Eligibility: an active Employee linked to the session user, whose employment type
  is Contract or Part-time (supervisors do not see it), and whose company is not in
  the handbook's excluded companies.
- Pages are read in order; progress never goes backwards.
- The acknowledgment is only accepted after the last page, and is stored with the
  date, IP address, browser and the exact statement accepted.

Employees have no permissions on Handbook or Handbook Read Progress; these methods
read and write them on their behalf. Back office reads the report through
get_progress_report (HR Manager or System Manager).
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from rpavs_platform.rpavs_platform.doctype.handbook.handbook import get_file_content

REPORT_ROLES = ("HR Manager", "System Manager")
STATUSES = ("Not Started", "In Progress", "Read", "Acknowledged")
USER_AGENT_MAX = 500
# Only contractors and part-time contractors read the handbook; supervisors (also an
# Employment Type) and employees without a type do not.
ELIGIBLE_EMPLOYMENT_TYPES = ("Contract", "Part-time")

PROGRESS_FIELDS = (
    "name",
    "status",
    "progress_percent",
    "max_page_reached",
    "last_page",
    "total_pages",
    "first_opened_on",
    "last_activity_on",
    "completed_on",
    "acknowledged",
    "acknowledged_on",
)


# --- Lookups ---------------------------------------------------------------------


def get_active_handbook():
    name = frappe.db.get_value("Handbook", {"is_active": 1}, "name", order_by="modified desc")
    return frappe.get_doc("Handbook", name) if name else None


def get_session_employee():
    return frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user, "status": "Active"},
        ["name", "employee_name", "company", "employment_type"],
        as_dict=True,
    )


def is_eligible(handbook, employee):
    return bool(
        handbook
        and employee
        and employee.employment_type in ELIGIBLE_EMPLOYMENT_TYPES
        and employee.company not in handbook.excluded_company_names()
    )


def get_eligible_context():
    """(handbook, employee) for the session user, or PermissionError."""
    handbook = get_active_handbook()
    employee = get_session_employee()
    if not is_eligible(handbook, employee):
        frappe.throw(_("The handbook is not available for your account."), frappe.PermissionError)
    return handbook, employee


def get_progress_name(handbook, employee):
    return frappe.db.get_value(
        "Handbook Read Progress", {"employee": employee.name, "handbook": handbook.name}, "name"
    )


def get_or_create_progress(handbook, employee):
    name = get_progress_name(handbook, employee)
    if name:
        return frappe.get_doc("Handbook Read Progress", name, for_update=True)

    doc = frappe.get_doc(
        {
            "doctype": "Handbook Read Progress",
            "employee": employee.name,
            "user": frappe.session.user,
            "company": employee.company,
            "handbook": handbook.name,
            "handbook_version": handbook.version,
            "total_pages": handbook.total_pages,
            "first_opened_on": now_datetime(),
        }
    )
    try:
        doc.insert(ignore_permissions=True)
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        # Two pages recorded at the same time; the other request created it.
        frappe.clear_messages()
        return frappe.get_doc("Handbook Read Progress", get_progress_name(handbook, employee), for_update=True)
    return doc


def get_user_agent():
    # No request when called from a console, a test or a background job.
    request = getattr(frappe.local, "request", None)
    user_agent = request.headers.get("User-Agent") if request else None
    return (user_agent or "")[:USER_AGENT_MAX] or None


def serialize_handbook(handbook):
    return {
        "name": handbook.name,
        "title": handbook.title,
        "version": handbook.version,
        "total_pages": handbook.total_pages,
        "acknowledgment_text": handbook.acknowledgment_text,
    }


def serialize_progress(progress, handbook):
    if not progress:
        return {
            "status": "Not Started",
            "progress_percent": 0,
            "max_page_reached": 0,
            "last_page": 0,
            "total_pages": handbook.total_pages,
            "first_opened_on": None,
            "last_activity_on": None,
            "completed_on": None,
            "acknowledged": 0,
            "acknowledged_on": None,
        }
    return {field: progress.get(field) for field in PROGRESS_FIELDS if field != "name"}


# --- Employee methods ------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def get_my_handbook():
    """The active handbook and the session user's progress, or {eligible: false}."""
    handbook = get_active_handbook()
    employee = get_session_employee()
    if not is_eligible(handbook, employee):
        return {"eligible": False}

    progress = frappe.db.get_value(
        "Handbook Read Progress",
        {"employee": employee.name, "handbook": handbook.name},
        list(PROGRESS_FIELDS),
        as_dict=True,
    )
    return {
        "eligible": True,
        "handbook": serialize_handbook(handbook),
        "progress": serialize_progress(progress, handbook),
    }


@frappe.whitelist(methods=["GET"])
def get_my_handbook_file():
    """The handbook PDF, only for eligible employees."""
    handbook, _employee = get_eligible_context()
    frappe.local.response.filename = f"{frappe.scrub(handbook.title)}_{frappe.scrub(handbook.version)}.pdf"
    frappe.local.response.filecontent = get_file_content(handbook.file)
    frappe.local.response.type = "pdf"


@frappe.whitelist(methods=["POST"])
def record_page(page):
    """Record that the employee is viewing `page` (1-based). Pages are read in order."""
    handbook, employee = get_eligible_context()
    page = cint(page)
    if not 1 <= page <= handbook.total_pages:
        frappe.throw(_("Page must be between 1 and {0}.").format(handbook.total_pages))

    doc = get_or_create_progress(handbook, employee)
    if page > doc.max_page_reached + 1:
        frappe.throw(_("Please read the handbook pages in order."))

    now = now_datetime()
    doc.last_page = page
    doc.max_page_reached = max(doc.max_page_reached, page)
    doc.last_activity_on = now
    if doc.max_page_reached >= doc.total_pages and not doc.completed_on:
        doc.completed_on = now
    doc.save(ignore_permissions=True)
    return serialize_progress(doc, handbook)


@frappe.whitelist(methods=["POST"])
def acknowledge(confirmed=None):
    """Store the employee's acknowledgment of the active handbook. Idempotent."""
    handbook, employee = get_eligible_context()
    if not cint(confirmed):
        frappe.throw(_("Please confirm that you have read and understand the handbook."))

    name = get_progress_name(handbook, employee)
    doc = frappe.get_doc("Handbook Read Progress", name, for_update=True) if name else None
    if not doc or doc.max_page_reached < doc.total_pages:
        frappe.throw(_("Please read the handbook up to the last page before acknowledging it."))

    if not doc.acknowledged:
        now = now_datetime()
        doc.acknowledged = 1
        doc.acknowledged_on = now
        doc.last_activity_on = now
        doc.acknowledgment_text = handbook.acknowledgment_text
        doc.ip_address = getattr(frappe.local, "request_ip", None)
        doc.user_agent = get_user_agent()
        doc.save(ignore_permissions=True)
    return serialize_progress(doc, handbook)


# --- Back office -----------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def get_progress_report(company=None, status=None):
    """
    Every active employee who must read the active handbook, with their progress.
    Employees who never opened it are included as Not Started.
    """
    frappe.only_for(REPORT_ROLES)

    handbook = get_active_handbook()
    if not handbook:
        return {"handbook": None, "summary": {s: 0 for s in STATUSES}, "rows": []}

    excluded = handbook.excluded_company_names()
    filters = {"status": "Active", "employment_type": ("in", ELIGIBLE_EMPLOYMENT_TYPES)}
    if company:
        filters["company"] = company
    employees = [
        e
        for e in frappe.get_all(
            "Employee",
            filters=filters,
            fields=["name", "employee_name", "company", "user_id"],
            order_by="employee_name asc",
            limit_page_length=0,
        )
        if e.company not in excluded
    ]

    progress_by_employee = {
        p.employee: p
        for p in frappe.get_all(
            "Handbook Read Progress",
            filters={"handbook": handbook.name},
            fields=["employee", *PROGRESS_FIELDS],
            limit_page_length=0,
        )
    }

    summary = {s: 0 for s in STATUSES}
    rows = []
    for e in employees:
        progress = serialize_progress(progress_by_employee.get(e.name), handbook)
        summary[progress["status"]] += 1
        if status and progress["status"] != status:
            continue
        rows.append(
            {
                "employee": e.name,
                "employee_name": e.employee_name,
                "company": e.company,
                "user_id": e.user_id,
                **progress,
            }
        )

    return {"handbook": serialize_handbook(handbook), "summary": summary, "rows": rows}
