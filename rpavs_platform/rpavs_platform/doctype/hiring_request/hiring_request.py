import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

from rpavs_platform.rpavs_platform.doctype.hiring_request_settings.hiring_request_settings import (
    get_notify_recipients,
)
from rpavs_platform.rpavs_platform.doctype.platform_feedback.platform_feedback import get_employee

# Set by the server from the session; the client (or a recruiter) cannot change them.
SUBMITTER_FIELDS = ("submitted_by", "submitted_on", "employee", "company")

TEXT_FIELDS = ("position_title", "location", "skills", "notes")
POSITION_TITLE_MAX = 140
LOCATION_MAX = 140
SKILLS_MAX = 2000
NOTES_MAX = 5000


class HiringRequest(Document):
    def before_insert(self):
        self.submitted_by = frappe.session.user
        self.submitted_on = now_datetime()
        self.status = "New"
        self.internal_notes = None
        self.employee, self.company = get_employee(self.submitted_by)

    def after_insert(self):
        self.notify_recruiting()

    def notify_recruiting(self):
        """Email everyone listed in Hiring Request Settings."""
        recipients = get_notify_recipients()
        if not recipients:
            return
        subject = _("New hiring request: {0}").format(self.position_title)
        if self.company:
            subject += f" ({self.company})"
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            template="new_hiring_request",
            args={"doc": self},
            reference_doctype=self.doctype,
            reference_name=self.name,
        )

    def before_validate(self):
        for field in TEXT_FIELDS:
            self.set(field, (self.get(field) or "").strip())

    def validate(self):
        for field, label, limit in (
            ("position_title", _("Position title"), POSITION_TITLE_MAX),
            ("location", _("Location"), LOCATION_MAX),
            ("skills", _("Required skills"), SKILLS_MAX),
            ("notes", _("Additional notes"), NOTES_MAX),
        ):
            if len(self.get(field) or "") > limit:
                frappe.throw(_("{0} must be {1} characters or fewer.").format(label, limit))

        before = self.get_doc_before_save()
        if before:
            for field in SUBMITTER_FIELDS:
                self.set(field, before.get(field))
            return

        # New requests only: a recruiter may later edit an old one whose date has passed.
        if self.expected_start_date and getdate(self.expected_start_date) < getdate(today()):
            frappe.throw(_("Expected start date cannot be in the past."))
        if not frappe.db.get_value("Hiring Experience Level", self.experience_level, "enabled"):
            frappe.throw(_("Choose a valid experience level."))
