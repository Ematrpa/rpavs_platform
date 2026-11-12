import frappe
from frappe.tests import IntegrationTestCase

from erpnext.setup.doctype.employee.test_employee import make_employee

# The test builds its own User and Employee on _Test Company (created by the ERPNext
# test fixtures). Generating the full ERPNext test record tree pulls in doctypes
# from apps that are not installed (e.g. Payment Gateway from `payments`).
IGNORE_TEST_RECORD_DEPENDENCIES = ["User", "Employee", "Company"]

SUPERVISOR = "feedback_supervisor@platform.test"
OTHER_SUPERVISOR = "feedback_other@platform.test"
REVIEWER = "feedback_reviewer@platform.test"


def make_user(email, role):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    user.add_roles(role)
    return user


def new_feedback(**kwargs):
    doc = frappe.get_doc(
        {
            "doctype": "Platform Feedback",
            "title": "  Add bulk timesheet approval  ",
            "category": "Enhancement Request",
            "description": "Approving one by one is slow.",
        }
    )
    doc.update(kwargs)
    return doc.insert()


class TestPlatformFeedback(IntegrationTestCase):
    def setUp(self):
        make_user(SUPERVISOR, "Client Supervisor")
        make_user(OTHER_SUPERVISOR, "Client Supervisor")
        self.employee = make_employee(SUPERVISOR, company="_Test Company")
        frappe.set_user(SUPERVISOR)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_submitter_comes_from_session_not_payload(self):
        doc = new_feedback(
            submitted_by="Administrator",
            status="Closed",
            internal_notes="spoofed",
        )

        self.assertEqual(doc.submitted_by, SUPERVISOR)
        self.assertEqual(doc.employee, self.employee)
        self.assertEqual(doc.company, "_Test Company")
        self.assertEqual(doc.status, "New")
        self.assertIsNone(doc.internal_notes)
        self.assertIsNotNone(doc.submitted_on)
        self.assertEqual(doc.title, "Add bulk timesheet approval")
        self.assertTrue(doc.name.startswith("FB-"))

    def test_new_feedback_emails_reviewers(self):
        frappe.set_user("Administrator")
        make_user(REVIEWER, "Feedback Reviewer")
        frappe.set_user(SUPERVISOR)
        doc = new_feedback()

        queued = frappe.get_all(
            "Email Queue",
            filters={"reference_doctype": "Platform Feedback", "reference_name": doc.name},
            pluck="name",
        )
        self.assertEqual(len(queued), 1)
        recipients = frappe.get_all(
            "Email Queue Recipient", filters={"parent": queued[0]}, pluck="recipient"
        )
        self.assertIn(REVIEWER, recipients)

    def test_other_company_is_rejected(self):
        # The supervisor's User Permissions (from their Employee) only allow their company.
        self.assertRaises(frappe.PermissionError, new_feedback, company="_Test Company 1")

    def test_invalid_category_is_rejected(self):
        self.assertRaises(frappe.ValidationError, new_feedback, category="Complaint")

    def test_blank_title_is_rejected(self):
        self.assertRaises(frappe.MandatoryError, new_feedback, title="   ")

    def test_supervisor_cannot_edit_after_submitting(self):
        doc = new_feedback()
        doc.status = "Closed"
        self.assertRaises(frappe.PermissionError, doc.save)

    def test_supervisor_only_sees_own_feedback(self):
        mine = new_feedback().name
        frappe.set_user(OTHER_SUPERVISOR)
        theirs = new_feedback().name

        visible = frappe.get_list("Platform Feedback", pluck="name")
        self.assertIn(theirs, visible)
        self.assertNotIn(mine, visible)

    def test_reviewer_cannot_change_submitter(self):
        doc = new_feedback()
        frappe.set_user("Administrator")
        doc = frappe.get_doc("Platform Feedback", doc.name)
        doc.status = "Under Review"
        doc.submitted_by = "Administrator"
        doc.save()

        doc.reload()
        self.assertEqual(doc.status, "Under Review")
        self.assertEqual(doc.submitted_by, SUPERVISOR)
