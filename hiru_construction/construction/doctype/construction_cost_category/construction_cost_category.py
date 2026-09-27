import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document


class ConstructionCostCategory(Document):
    def validate(self):
        previous = self.get_doc_before_save()
        if previous and (previous.scope != self.scope or previous.project != self.project):
            used = frappe.db.sql("""select i.name from `tabConstruction Cost Plan Item` i
                join `tabConstruction Cost Plan` p on p.name=i.parent
                where i.category=%s and p.docstatus=1 limit 1""", self.name)
            if used:
                frappe.throw(_("A category used by a submitted cost plan cannot change scope or project."))
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
