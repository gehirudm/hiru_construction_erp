import math

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class ConstructionCostPlan(Document):
    def validate(self):
        self.company = frappe.get_cached_value("Project", self.project, "company")
        if not self.company:
            frappe.throw(_("Set a company on the project before creating a cost plan."))
        self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
        if self.version_kind not in ("Tender baseline", "Approved revision"):
            frappe.throw(_("Choose a tender baseline or an approved revision."))
        if not self.items:
            frappe.throw(_("Add at least one cost line."))
        accounts = set()
        for row in self.items:
            category = frappe.get_cached_doc("Construction Cost Category", row.category)
            if category.disabled:
                frappe.throw(_("Category {0} is disabled.").format(category.category_name))
            if category.scope == "Project" and category.project != self.project:
                frappe.throw(_("Category {0} belongs to another project.").format(category.category_name))
            if not row.account:
                frappe.throw(_("Select an expense account on each cost line."))
            account = frappe.get_cached_doc("Account", row.account)
            if (account.company != self.company or account.root_type != "Expense"
                    or account.is_group or account.disabled):
                frappe.throw(_("Account {0} must be an enabled expense ledger in {1}.").format(
                    row.account, self.company))
            if row.account in accounts:
                frappe.throw(_("Map each expense account only once per plan."))
            accounts.add(row.account)
            for field in ("original_estimate", "approved_revision", "contingency"):
                amount = flt(row.get(field))
                if not math.isfinite(amount) or amount < 0:
                    frappe.throw(_("Cost amounts must be finite and non-negative."))
        self.validate_baseline()
        for field in ("original_estimate", "approved_revision", "contingency"):
            self.set("total_" + field, sum(flt(row.get(field)) for row in self.items))
        if self.docstatus == 0:
            self.status = "Draft"
            self.revision_number = 0

    def validate_baseline(self):
        if self.version_kind == "Tender baseline":
            if self.baseline:
                frappe.throw(_("A tender baseline cannot reference another baseline."))
            if any(flt(row.approved_revision) for row in self.items):
                frappe.throw(_("Enter tender amounts in Original Tender Estimate; revision amounts belong in a revision."))
            return
        if not self.baseline:
            frappe.throw(_("Select a submitted tender baseline for this revision."))
        baseline = frappe.get_doc(self.doctype, self.baseline)
        if (baseline.project != self.project or baseline.docstatus != 1
                or baseline.version_kind != "Tender baseline"):
            frappe.throw(_("The baseline must be a submitted tender for the same project."))
        original = {row.account: row for row in baseline.items}
        current = {row.account: row for row in self.items}
        if original.keys() - current.keys():
            frappe.throw(_("Keep all original tender accounts in revisions; use a zero revised amount to remove their budget."))
        for account, row in current.items():
            source = original.get(account)
            if source:
                if row.category != source.category or flt(row.original_estimate, 2) != flt(source.original_estimate, 2):
                    frappe.throw(_("Revisions must preserve original tender categories and estimates."))
            elif flt(row.original_estimate):
                frappe.throw(_("New revision lines must have a zero original tender estimate."))

    def lock_project(self):
        # Serialize approval and cancellation for a project, including concurrent requests.
        frappe.db.sql("select name from `tabProject` where name=%s for update", self.project)
        self._locked_plans = frappe.db.sql("""select name, docstatus, version_kind, baseline,
            revision_number, status from `tabConstruction Cost Plan`
            where project=%s for update""", self.project, as_dict=True)

    def before_submit(self):
        self.lock_project()
        if self.version_kind == "Approved revision" and not any(
                row.name == self.baseline and row.docstatus == 1
                and row.version_kind == "Tender baseline" for row in self._locked_plans):
            frappe.throw(_("The tender baseline is no longer submitted."))
        self.validate_baseline()
        if self.version_kind == "Tender baseline":
            if any(row.version_kind == "Tender baseline" and row.docstatus == 1
                   for row in self._locked_plans):
                frappe.throw(_("This project already has a submitted tender baseline."))
        else:
            number = max((row.revision_number or 0 for row in self._locked_plans), default=0)
            self.revision_number = number + 1
        self.status = "Approved"

    def on_submit(self):
        if self.version_kind == "Approved revision":
            for row in self._locked_plans:
                if row.name != self.name and row.version_kind == "Approved revision" and row.docstatus == 1:
                    frappe.db.set_value(self.doctype, row.name, "status", "Superseded")

    def before_cancel(self):
        self.lock_project()
        if self.version_kind == "Tender baseline" and any(
                row.baseline == self.name and row.docstatus == 1 for row in self._locked_plans):
            frappe.throw(_("Cancel submitted revisions before cancelling their tender baseline."))

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        if self.version_kind == "Approved revision":
            remaining = sorted((row for row in self._locked_plans if row.name != self.name
                and row.version_kind == "Approved revision" and row.docstatus == 1),
                key=lambda row: row.revision_number or 0, reverse=True)
            for i, row in enumerate(remaining):
                frappe.db.set_value(self.doctype, row.name, "status", "Approved" if i == 0 else "Superseded")
