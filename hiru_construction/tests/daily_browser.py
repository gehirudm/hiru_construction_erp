"""Stable UI fixtures, only on the isolated test site."""
import frappe


def prepare():
    if not frappe.conf.get("hiru_test"):
        raise RuntimeError("Browser fixtures require the isolated test site")
    company = frappe.get_doc("Company", "Cost Controls Test")
    project = "UI-DAILY-PROJECT"
    if not frappe.db.exists("Project", project):
        frappe.get_doc({"doctype": "Project", "project_name": "Daily view test project",
            "company": company.name, "cost_center": company.cost_center}).insert(set_name=project)
    if not frappe.db.exists("Construction Cost Plan", "UI-DAILY-BUDGET"):
        category = frappe.db.get_value("Construction Cost Category", {"category_name": "Transport", "scope": "Global"}, "name")
        frappe.get_doc({"doctype": "Construction Cost Plan", "plan_name": "UI-DAILY-BUDGET",
            "project": project, "version_kind": "Tender baseline", "items": [{"category": category,
                "account": company.default_expense_account, "original_estimate": 10000}]}).insert().submit()
    if not frappe.db.exists("Supplier", "Daily UI Supplier"):
        frappe.get_doc({"doctype": "Supplier", "supplier_name": "Daily UI Supplier",
            "supplier_group": "All Supplier Groups", "supplier_type": "Company"}).insert()
    frappe.db.commit()
