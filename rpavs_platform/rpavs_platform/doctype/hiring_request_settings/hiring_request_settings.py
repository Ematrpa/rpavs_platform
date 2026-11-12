import frappe
from frappe import _
from frappe.model.document import Document


class HiringRequestSettings(Document):
    def validate(self):
        seen = set()
        for row in self.notify_recipients:
            row.email = (row.email or "").strip().lower()
            if row.email in seen:
                frappe.throw(_("Row {0}: {1} is already in the list.").format(row.idx, row.email))
            seen.add(row.email)


def get_notify_recipients():
    settings = frappe.get_cached_doc("Hiring Request Settings")
    return [row.email for row in settings.notify_recipients if row.enabled and row.email]
