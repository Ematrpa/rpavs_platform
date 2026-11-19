import io

import frappe
from frappe.tests import IntegrationTestCase
from pypdf import PdfWriter

from erpnext.setup.doctype.employee.test_employee import make_employee
from rpavs_platform.api import handbook as api

# See test_platform_feedback: the full ERPNext test record tree pulls in apps that
# are not installed.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User", "Employee", "Company"]

CONTRACTOR = "handbook_contractor@platform.test"
EXCLUDED_CONTRACTOR = "handbook_excluded@platform.test"
NO_EMPLOYEE = "handbook_noemployee@platform.test"
HR = "handbook_hr@platform.test"

CLIENT_COMPANY = "_Test Company"
EXCLUDED_COMPANY = "_Test Company 1"
PAGES = 3


def make_user(email, role):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    user.add_roles(role)
    return user


def make_pdf(pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def make_handbook(version, pages=PAGES, excluded=(EXCLUDED_COMPANY,), is_active=1):
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": f"handbook-{version}.pdf",
            "is_private": 1,
            "content": make_pdf(pages),
        }
    ).insert(ignore_permissions=True)
    return frappe.get_doc(
        {
            "doctype": "Handbook",
            "title": "Test Handbook",
            "version": version,
            "is_active": is_active,
            "file": file_doc.file_url,
            "acknowledgment_text": "I read it.",
            "excluded_companies": [{"company": c} for c in excluded],
        }
    ).insert(ignore_permissions=True)


class TestHandbook(IntegrationTestCase):
    def setUp(self):
        frappe.set_user("Administrator")
        frappe.db.delete("Handbook Read Progress")
        frappe.db.delete("Handbook Excluded Company")
        frappe.db.delete("Handbook")
        make_user(CONTRACTOR, "Employee Self Service")
        make_user(EXCLUDED_CONTRACTOR, "Employee Self Service")
        make_user(NO_EMPLOYEE, "Employee Self Service")
        make_user(HR, "HR Manager")
        self.employee = make_employee(CONTRACTOR, company=CLIENT_COMPANY)
        self.excluded_employee = make_employee(EXCLUDED_CONTRACTOR, company=EXCLUDED_COMPANY)
        self.handbook = make_handbook("t-1")

    def tearDown(self):
        frappe.set_user("Administrator")

    def read_all(self):
        for page in range(1, PAGES + 1):
            progress = api.record_page(page)
        return progress

    # --- Handbook ----------------------------------------------------------------

    def test_total_pages_is_counted_from_pdf(self):
        self.assertEqual(self.handbook.total_pages, PAGES)

    def test_only_one_active_handbook(self):
        newer = make_handbook("t-2")
        self.assertEqual(frappe.db.get_value("Handbook", self.handbook.name, "is_active"), 0)
        self.assertEqual(api.get_active_handbook().name, newer.name)

    def test_public_file_is_rejected(self):
        doc = frappe.get_doc(
            {"doctype": "File", "file_name": "public.pdf", "is_private": 0, "content": make_pdf(1)}
        ).insert(ignore_permissions=True)
        handbook = frappe.get_doc(
            {"doctype": "Handbook", "title": "x", "version": "t-public", "file": doc.file_url}
        )
        self.assertRaises(frappe.ValidationError, handbook.insert)

    # --- Eligibility -------------------------------------------------------------

    def test_client_contractor_is_eligible(self):
        frappe.set_user(CONTRACTOR)
        data = api.get_my_handbook()
        self.assertTrue(data["eligible"])
        self.assertEqual(data["handbook"]["total_pages"], PAGES)
        self.assertEqual(data["progress"]["status"], "Not Started")

    def test_excluded_company_is_not_eligible(self):
        frappe.set_user(EXCLUDED_CONTRACTOR)
        self.assertEqual(api.get_my_handbook(), {"eligible": False})
        self.assertRaises(frappe.PermissionError, api.record_page, 1)
        self.assertRaises(frappe.PermissionError, api.get_my_handbook_file)

    def test_user_without_employee_is_not_eligible(self):
        frappe.set_user(NO_EMPLOYEE)
        self.assertEqual(api.get_my_handbook(), {"eligible": False})

    def test_no_active_handbook(self):
        frappe.db.set_value("Handbook", self.handbook.name, "is_active", 0)
        frappe.set_user(CONTRACTOR)
        self.assertEqual(api.get_my_handbook(), {"eligible": False})

    def test_file_is_served_to_eligible_employee(self):
        frappe.set_user(CONTRACTOR)
        api.get_my_handbook_file()
        self.assertEqual(frappe.local.response.type, "pdf")
        self.assertTrue(frappe.local.response.filecontent.startswith(b"%PDF"))

    # --- Progress ----------------------------------------------------------------

    def test_progress_is_recorded_per_page(self):
        frappe.set_user(CONTRACTOR)
        api.record_page(1)
        progress = api.record_page(2)
        self.assertEqual(progress["max_page_reached"], 2)
        self.assertEqual(progress["status"], "In Progress")
        self.assertAlmostEqual(progress["progress_percent"], 66.67)

        # Going back keeps the furthest page.
        progress = api.record_page(1)
        self.assertEqual(progress["last_page"], 1)
        self.assertEqual(progress["max_page_reached"], 2)

        doc = frappe.get_doc("Handbook Read Progress", {"employee": self.employee})
        self.assertEqual(doc.company, CLIENT_COMPANY)
        self.assertEqual(doc.handbook_version, "t-1")
        self.assertIsNotNone(doc.first_opened_on)

    def test_pages_must_be_read_in_order(self):
        frappe.set_user(CONTRACTOR)
        self.assertRaises(frappe.ValidationError, api.record_page, 3)
        self.assertRaises(frappe.ValidationError, api.record_page, PAGES + 1)
        self.assertRaises(frappe.ValidationError, api.record_page, 0)

    def test_reaching_last_page_marks_read(self):
        frappe.set_user(CONTRACTOR)
        progress = self.read_all()
        self.assertEqual(progress["status"], "Read")
        self.assertEqual(progress["progress_percent"], 100)
        self.assertIsNotNone(progress["completed_on"])

    # --- Acknowledgment ----------------------------------------------------------

    def test_cannot_acknowledge_before_last_page(self):
        frappe.set_user(CONTRACTOR)
        api.record_page(1)
        self.assertRaises(frappe.ValidationError, api.acknowledge, confirmed=1)

    def test_acknowledge_requires_confirmation(self):
        frappe.set_user(CONTRACTOR)
        self.read_all()
        self.assertRaises(frappe.ValidationError, api.acknowledge)

    def test_acknowledge_stores_evidence_once(self):
        frappe.set_user(CONTRACTOR)
        self.read_all()
        progress = api.acknowledge(confirmed=1)
        self.assertEqual(progress["status"], "Acknowledged")
        first = progress["acknowledged_on"]

        doc = frappe.get_doc("Handbook Read Progress", {"employee": self.employee})
        self.assertEqual(doc.acknowledgment_text, "I read it.")
        self.assertEqual(doc.user, CONTRACTOR)

        # Idempotent: a second call keeps the original date.
        self.assertEqual(api.acknowledge(confirmed=1)["acknowledged_on"], first)

    def test_acknowledgment_cannot_be_withdrawn(self):
        frappe.set_user(CONTRACTOR)
        self.read_all()
        api.acknowledge(confirmed=1)
        frappe.set_user("Administrator")
        doc = frappe.get_doc("Handbook Read Progress", {"employee": self.employee})
        doc.acknowledged = 0
        self.assertRaises(frappe.ValidationError, doc.save)

    def test_new_version_requires_reading_again(self):
        frappe.set_user(CONTRACTOR)
        self.read_all()
        api.acknowledge(confirmed=1)
        frappe.set_user("Administrator")
        make_handbook("t-2")
        frappe.set_user(CONTRACTOR)
        data = api.get_my_handbook()
        self.assertEqual(data["handbook"]["version"], "t-2")
        self.assertEqual(data["progress"]["status"], "Not Started")

    def test_employee_cannot_read_progress_records_directly(self):
        frappe.set_user(CONTRACTOR)
        api.record_page(1)
        self.assertRaises(
            frappe.PermissionError, frappe.get_list, "Handbook Read Progress", limit_page_length=1
        )

    # --- Report ------------------------------------------------------------------

    def test_report_lists_eligible_employees_with_not_started(self):
        frappe.set_user(CONTRACTOR)
        api.record_page(1)
        frappe.set_user(HR)
        report = api.get_progress_report()
        by_employee = {r["employee"]: r for r in report["rows"]}

        self.assertEqual(by_employee[self.employee]["status"], "In Progress")
        self.assertNotIn(self.excluded_employee, by_employee)
        self.assertGreaterEqual(report["summary"]["In Progress"], 1)

        only_started = api.get_progress_report(status="In Progress")["rows"]
        self.assertEqual({r["status"] for r in only_started}, {"In Progress"})

    def test_report_is_for_hr_only(self):
        frappe.set_user(CONTRACTOR)
        self.assertRaises(frappe.PermissionError, api.get_progress_report)
