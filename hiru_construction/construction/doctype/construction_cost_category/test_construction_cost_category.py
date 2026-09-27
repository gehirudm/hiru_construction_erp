import frappe
from frappe.tests import IntegrationTestCase

# Create only the projects needed below; avoid ERPNext's unrelated accounting fixtures.
IGNORE_TEST_RECORD_DEPENDENCIES = ["Project"]


class TestConstructionCostCategory(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.get("hiru_test"):
            raise RuntimeError("Use make test to run on the isolated test site")
        super().setUpClass()

    def category(self, name, **values):
        return frappe.get_doc({"doctype": "Construction Cost Category", "category_name": name,
                               "scope": "Global", **values}).insert()

    def test_normalized_duplicate_rejected(self):
        name = "Test " + frappe.generate_hash(length=10)
        first = self.category(name)
        with self.assertRaises(frappe.ValidationError):
            self.category("  " + name.upper() + "  ")
        first.description = "Updated without changing scope"
        first.save()

    def test_project_categories_are_independent(self):
        name = "Test " + frappe.generate_hash(length=10)
        projects = [frappe.get_doc({"doctype": "Project", "project_name": name + str(i),
                                   "company": "Cost Controls Test"}).insert()
                    for i in range(2)]
        global_category = self.category(name)
        local = [self.category(name, scope="Project", project=p.name) for p in projects]
        self.assertEqual(len({global_category.scope_key, *(c.scope_key for c in local)}), 3)
        with self.assertRaises(frappe.ValidationError):
            self.category(name, scope="Project", project=projects[0].name)

    def test_invalid_scope_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            self.category("Missing Project", scope="Project")
        with self.assertRaises(frappe.ValidationError):
            self.category(" ")

    def test_guest_cannot_create(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                self.category("Unauthorized category")
        finally:
            frappe.set_user("Administrator")
