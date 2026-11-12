from frappe.model.document import Document


class HiringExperienceLevel(Document):
    def before_validate(self):
        self.level_name = (self.level_name or "").strip()
