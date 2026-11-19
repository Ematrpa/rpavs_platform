import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

# Once set, these are evidence and never change.
IMMUTABLE_FIELDS = ("employee", "user", "handbook", "handbook_version", "total_pages", "first_opened_on")
ACKNOWLEDGMENT_FIELDS = ("acknowledged_on", "acknowledgment_text", "ip_address", "user_agent")


class HandbookReadProgress(Document):
    def before_validate(self):
        self.total_pages = cint(self.total_pages)
        self.max_page_reached = cint(self.max_page_reached)
        self.last_page = cint(self.last_page)
        self.progress_percent = (
            flt(100.0 * self.max_page_reached / self.total_pages, 2) if self.total_pages else 0
        )
        self.status = compute_status(self)

    def validate(self):
        if self.total_pages < 1:
            frappe.throw(_("Total pages must be at least 1."))
        if not 0 <= self.max_page_reached <= self.total_pages:
            frappe.throw(_("Furthest page reached must be between 0 and {0}.").format(self.total_pages))
        if not 0 <= self.last_page <= self.max_page_reached:
            frappe.throw(_("Last page viewed cannot be past the furthest page reached."))
        if self.acknowledged and self.max_page_reached < self.total_pages:
            frappe.throw(_("The handbook can only be acknowledged after reaching the last page."))

        before = self.get_doc_before_save()
        if before:
            self.validate_against(before)

    def validate_against(self, before):
        for field in IMMUTABLE_FIELDS:
            if before.get(field) and self.get(field) != before.get(field):
                frappe.throw(_("{0} cannot be changed.").format(self.meta.get_label(field)))
        if self.max_page_reached < cint(before.max_page_reached):
            frappe.throw(_("Reading progress cannot go backwards."))
        if before.completed_on and self.completed_on != before.completed_on:
            frappe.throw(_("Completed On cannot be changed."))
        if before.acknowledged:
            if not self.acknowledged:
                frappe.throw(_("An acknowledgment cannot be withdrawn."))
            for field in ACKNOWLEDGMENT_FIELDS:
                if self.get(field) != before.get(field):
                    frappe.throw(_("{0} cannot be changed.").format(self.meta.get_label(field)))


def compute_status(doc):
    if doc.acknowledged:
        return "Acknowledged"
    if doc.total_pages and doc.max_page_reached >= doc.total_pages:
        return "Read"
    if doc.max_page_reached > 0:
        return "In Progress"
    return "Not Started"


def on_doctype_update():
    # One progress record per employee and handbook version.
    frappe.db.add_unique(
        "Handbook Read Progress", ["employee", "handbook"], constraint_name="unique_employee_handbook"
    )
