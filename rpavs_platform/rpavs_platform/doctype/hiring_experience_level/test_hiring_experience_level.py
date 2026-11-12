import frappe
from frappe.tests import IntegrationTestCase

from rpavs_platform.install import DEFAULT_EXPERIENCE_LEVELS, ensure_experience_levels


class TestHiringExperienceLevel(IntegrationTestCase):
    def test_defaults_are_seeded(self):
        ensure_experience_levels()
        for level in DEFAULT_EXPERIENCE_LEVELS:
            self.assertTrue(frappe.db.exists("Hiring Experience Level", level))

    def test_seed_does_not_restore_levels_recruiters_removed(self):
        ensure_experience_levels()
        frappe.delete_doc("Hiring Experience Level", "Junior", force=True)
        ensure_experience_levels()
        self.assertFalse(frappe.db.exists("Hiring Experience Level", "Junior"))
