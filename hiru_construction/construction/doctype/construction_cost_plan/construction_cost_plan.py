import frappe
from frappe import _
from frappe.model.document import Document


class ConstructionCostPlan(Document):
    def validate(self):
        project = frappe.get_cached_doc("Project", self.project)
        self.company = project.company
        self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
        if not self.items:
            frappe.throw(_("Add at least one cost line."))
        if self.version_kind == "Tender baseline":
            existing = frappe.db.exists("Construction Cost Plan", {
                "project": self.project, "version_kind": "Tender baseline", "name": ["!=", self.name]
            })
            if existing:
                frappe.throw(_("A project can have only one tender baseline."))
        for row in self.items:
            category = frappe.get_cached_doc("Construction Cost Category", row.category)
            if category.disabled:
                frappe.throw(_("Category {0} is disabled.").format(category.category_name))
            if category.scope == "Project" and category.project != self.project:
                frappe.throw(_("Category {0} belongs to another project.").format(category.category_name))
            if row.account and frappe.db.get_value("Account", row.account, "root_type") != "Expense":
                frappe.throw(_("Cost line account {0} must be an Expense account.").format(row.account))
            for field in ("original_estimate", "approved_revision", "contingency"):
                if row.get(field) is not None and row.get(field) < 0:
                    frappe.throw(_("{0} cannot be negative.").format(frappe.unscrub(field)))
        self.total_original_estimate = sum(row.original_estimate or 0 for row in self.items)
        self.total_approved_revision = sum(row.approved_revision or 0 for row in self.items)
        self.total_contingency = sum(row.contingency or 0 for row in self.items)

    def on_submit(self):
        self.db_set("status", "Approved")
        if self.version_kind == "Approved revision":
            frappe.db.set_value("Construction Cost Plan", {
                "project": self.project, "version_kind": "Approved revision", "name": ["!=", self.name],
                "status": "Approved"
            }, "status", "Superseded", update_modified=False)

    def on_cancel(self):
        self.db_set("status", "Draft")
