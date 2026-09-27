import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document


class ConstructionCostCategory(Document):
    def validate(self):
        self.category_name = " ".join((self.category_name or "").split())
        if not self.category_name:
            frappe.throw(_("Enter a category name."))
        if self.scope == "Project":
            if not self.project:
                frappe.throw(_("Select a project for a project category."))
        elif self.scope == "Global":
            if self.project:
                frappe.throw(_("A global category cannot be assigned to a project."))
        else:
            frappe.throw(_("Choose Global or Project scope."))
        identity = json.dumps([self.scope, self.project or "", self.category_name.casefold()])
        self.scope_key = hashlib.sha256(identity.encode()).hexdigest()
        duplicate = frappe.db.get_value(self.doctype, {"scope_key": self.scope_key}, "name")
        if duplicate and duplicate != self.name:
            frappe.throw(_("A category with this name already exists in this scope."))
