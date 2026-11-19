import io

import frappe
from frappe import _
from frappe.model.document import Document
from pypdf import PdfReader
from pypdf.errors import PdfReadError


class Handbook(Document):
    def validate(self):
        self.title = (self.title or "").strip()
        self.version = (self.version or "").strip()
        self.validate_file()
        self.validate_excluded_companies()

    def on_update(self):
        if self.is_active:
            # Only one handbook is shown on the platform at a time.
            frappe.db.set_value(
                "Handbook",
                {"name": ("!=", self.name), "is_active": 1},
                "is_active",
                0,
                update_modified=False,
            )

    def after_rename(self, old, new, merge=False):
        # A rename corrects the version label of the same document: Frappe already
        # updated `version` and the progress links, so keep the stored label in step.
        # (To make everyone read it again, a new Handbook is created instead.)
        frappe.db.set_value(
            "Handbook Read Progress",
            {"handbook": new},
            "handbook_version",
            new,
            update_modified=False,
        )
        self.add_comment(
            "Info",
            _("Version renamed from {0} to {1}; existing reading progress and acknowledgments were kept.").format(
                old, new
            ),
        )

    def validate_file(self):
        if not self.file.startswith("/private/files/"):
            frappe.throw(_("The handbook PDF must be uploaded as a private file."))
        if not self.file.lower().endswith(".pdf"):
            frappe.throw(_("The handbook must be a PDF file."))

        self.total_pages = count_pages(get_file_content(self.file))
        if not self.total_pages:
            frappe.throw(_("The handbook PDF has no pages."))

    def validate_excluded_companies(self):
        seen = set()
        for row in self.excluded_companies:
            if row.company in seen:
                frappe.throw(_("Company {0} is excluded twice.").format(row.company))
            seen.add(row.company)

    def excluded_company_names(self):
        return {row.company for row in self.excluded_companies}


def get_file_content(file_url):
    file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not file_name:
        frappe.throw(_("File {0} was not found.").format(file_url))
    # Not File.get_content(): it decodes the bytes to text when they happen to be valid UTF-8.
    with open(frappe.get_doc("File", file_name).get_full_path(), "rb") as f:
        return f.read()


def count_pages(content):
    try:
        return len(PdfReader(io.BytesIO(content)).pages)
    except (PdfReadError, ValueError, TypeError):
        frappe.throw(_("The handbook file is not a valid PDF."))
