import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from erpnext.setup.doctype.employee.test_employee import make_employee

from rpavs_platform.install import ensure_experience_levels, ensure_hiring_request_recipients

# See test_platform_feedback: build our own User/Employee instead of the full test tree.
IGNORE_TEST_RECORD_DEPENDENCIES = ["User", "Employee", "Company"]

CLIENT_ADMIN = "hiring_admin@platform.test"
OTHER_ADMIN = "hiring_other_admin@platform.test"
SUPERVISOR = "hiring_supervisor@platform.test"
RECRUITER = "hiring_recruiter@platform.test"
NOTIFY_TO = "scortez@rpapm.com"


def make_user(email, role):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    user = frappe.get_doc("User", email)
    user.add_roles(role)
    return user


def set_recipients(*rows, check_permissions=False):
    """rows: (email, enabled) pairs."""
    settings = frappe.get_single("Hiring Request Settings")
    settings.notify_recipients = []
    for email, enabled in rows:
        settings.append("notify_recipients", {"email": email, "enabled": enabled})
    settings.save(ignore_permissions=not check_permissions)


def queued_recipients(doc):
    queued = frappe.get_all(
        "Email Queue",
        filters={"reference_doctype": "Hiring Request", "reference_name": doc.name},
        pluck="name",
    )
    return queued, frappe.get_all(
        "Email Queue Recipient", filters={"parent": ["in", queued or [""]]}, pluck="recipient"
    )


def new_request(**kwargs):
    doc = frappe.get_doc(
        {
            "doctype": "Hiring Request",
            "position_title": "  Leasing Coordinator  ",
            "experience_level": "Mid",
            "location": "Remote (US hours)",
            "skills": "Yardi, tenant communication",
            "expected_start_date": add_days(today(), 30),
        }
    )
    doc.update(kwargs)
    return doc.insert()


class TestHiringRequest(IntegrationTestCase):
    def setUp(self):
        ensure_experience_levels()
        set_recipients((NOTIFY_TO, 1))
        make_user(CLIENT_ADMIN, "Client Admin")
        make_user(OTHER_ADMIN, "Client Admin")
        self.employee = make_employee(CLIENT_ADMIN, company="_Test Company")
        frappe.set_user(CLIENT_ADMIN)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_submitter_comes_from_session_not_payload(self):
        doc = new_request(submitted_by="Administrator", status="Filled", internal_notes="spoofed")

        self.assertEqual(doc.submitted_by, CLIENT_ADMIN)
        self.assertEqual(doc.employee, self.employee)
        self.assertEqual(doc.company, "_Test Company")
        self.assertEqual(doc.status, "New")
        self.assertIsNone(doc.internal_notes)
        self.assertIsNotNone(doc.submitted_on)
        self.assertEqual(doc.position_title, "Leasing Coordinator")
        self.assertTrue(doc.name.startswith("HIRE-"))

    def test_new_request_emails_listed_recipients_only(self):
        frappe.set_user("Administrator")
        make_user(RECRUITER, "Recruiter")
        frappe.set_user(CLIENT_ADMIN)
        queued, recipients = queued_recipients(new_request())

        self.assertEqual(len(queued), 1)
        self.assertIn(NOTIFY_TO, recipients)
        self.assertNotIn(RECRUITER, recipients)

    def test_recruiter_can_add_recipients_and_disable_one(self):
        frappe.set_user("Administrator")
        make_user(RECRUITER, "Recruiter")
        frappe.set_user(RECRUITER)
        set_recipients(
            (NOTIFY_TO, 1),
            ("teri@platform.test", 1),
            ("off@platform.test", 0),
            check_permissions=True,
        )

        frappe.set_user(CLIENT_ADMIN)
        _, recipients = queued_recipients(new_request())
        self.assertEqual(set(recipients), {NOTIFY_TO, "teri@platform.test"})

    def test_client_admin_cannot_edit_recipients(self):
        self.assertRaises(
            frappe.PermissionError, set_recipients, (CLIENT_ADMIN, 1), check_permissions=True
        )

    def test_no_recipients_sends_no_email(self):
        set_recipients()
        queued, _ = queued_recipients(new_request())
        self.assertEqual(queued, [])

    def test_duplicate_recipient_is_rejected(self):
        self.assertRaises(
            frappe.ValidationError,
            set_recipients,
            (NOTIFY_TO, 1),
            (" SCortez@rpapm.com ", 1),
        )

    def test_seed_does_not_refill_a_list_recruiting_edited(self):
        set_recipients(("teri@platform.test", 1))
        ensure_hiring_request_recipients()
        emails = [r.email for r in frappe.get_single("Hiring Request Settings").notify_recipients]
        self.assertEqual(emails, ["teri@platform.test"])

    def test_only_client_admin_can_submit(self):
        frappe.set_user("Administrator")
        make_user(SUPERVISOR, "Client Supervisor")
        frappe.set_user(SUPERVISOR)
        self.assertRaises(frappe.PermissionError, new_request)

    def test_guest_cannot_submit(self):
        frappe.set_user("Guest")
        self.assertRaises(frappe.PermissionError, new_request)

    def test_other_company_is_rejected(self):
        self.assertRaises(frappe.PermissionError, new_request, company="_Test Company 1")

    def test_disabled_level_is_rejected(self):
        frappe.set_user("Administrator")
        frappe.db.set_value("Hiring Experience Level", "Senior", "enabled", 0)
        frappe.set_user(CLIENT_ADMIN)
        self.assertRaises(frappe.ValidationError, new_request, experience_level="Senior")

    def test_unknown_level_is_rejected(self):
        self.assertRaises(frappe.LinkValidationError, new_request, experience_level="Principal")

    def test_past_start_date_is_rejected(self):
        self.assertRaises(
            frappe.ValidationError, new_request, expected_start_date=add_days(today(), -1)
        )

    def test_blank_skills_is_rejected(self):
        self.assertRaises(frappe.MandatoryError, new_request, skills="   ")

    def test_client_admin_cannot_edit_after_submitting(self):
        doc = new_request()
        doc.status = "Closed"
        self.assertRaises(frappe.PermissionError, doc.save)

    def test_client_admin_only_sees_own_requests(self):
        mine = new_request().name
        frappe.set_user(OTHER_ADMIN)
        theirs = new_request().name

        visible = frappe.get_list("Hiring Request", pluck="name")
        self.assertIn(theirs, visible)
        self.assertNotIn(mine, visible)

    def test_recruiter_updates_status_but_not_submitter(self):
        name = new_request().name
        frappe.set_user("Administrator")
        make_user(RECRUITER, "Recruiter")
        frappe.set_user(RECRUITER)

        doc = frappe.get_doc("Hiring Request", name)
        doc.status = "Sourcing"
        doc.internal_notes = "Two candidates shortlisted"
        doc.submitted_by = RECRUITER
        doc.save()

        doc.reload()
        self.assertEqual(doc.status, "Sourcing")
        self.assertEqual(doc.internal_notes, "Two candidates shortlisted")
        self.assertEqual(doc.submitted_by, CLIENT_ADMIN)
