import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

# Set by the server from the session; the client (or a reviewer) cannot change them.
SUBMITTER_FIELDS = ("submitted_by", "submitted_on", "employee", "company")

TITLE_MAX = 140
DESCRIPTION_MAX = 5000


class PlatformFeedback(Document):
    def before_insert(self):
        self.submitted_by = frappe.session.user
        self.submitted_on = now_datetime()
        self.status = "New"
        self.internal_notes = None
        self.employee, self.company = get_employee(self.submitted_by)

    def before_validate(self):
        self.title = (self.title or "").strip()
        self.description = (self.description or "").strip()

    def validate(self):
        if len(self.title) > TITLE_MAX:
            frappe.throw(_("Title must be {0} characters or fewer.").format(TITLE_MAX))
        if len(self.description) > DESCRIPTION_MAX:
            frappe.throw(_("Description must be {0} characters or fewer.").format(DESCRIPTION_MAX))

        before = self.get_doc_before_save()
        if before:
            for field in SUBMITTER_FIELDS:
                self.set(field, before.get(field))


def get_employee(user):
    """Active Employee linked to `user`, and its company. (None, None) if there is none."""
    row = frappe.db.get_value(
        "Employee", {"user_id": user, "status": "Active"}, ["name", "company"], as_dict=True
    )
    return (row.name, row.company) if row else (None, None)
