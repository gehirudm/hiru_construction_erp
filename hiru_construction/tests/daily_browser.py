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
    from frappe.utils import add_days, nowdate
    if not frappe.db.exists("Project", "UI-SITE-PROJECT"):
        frappe.get_doc({"doctype": "Project", "project_name": "Site workflow test",
            "company": company.name, "cost_center": company.cost_center}).insert(set_name="UI-SITE-PROJECT")
        category = frappe.db.get_value("Construction Cost Category", {"category_name": "Fuel", "scope": "Global"}, "name")
        frappe.get_doc({"doctype": "Construction Cost Plan", "plan_name": "UI-SITE-BUDGET",
            "project": "UI-SITE-PROJECT", "version_kind": "Tender baseline", "items": [{"category": category,
                "account": company.default_expense_account, "original_estimate": 20000}]}).insert().submit()
    if not frappe.db.exists("Employee", "UI-SITE-WORKER"):
        frappe.get_doc({"doctype": "Employee", "first_name": "UI Site Worker", "gender": "Male",
            "date_of_birth": "1990-01-01", "date_of_joining": add_days(nowdate(), -30),
            "company": company.name, "status": "Active", "custom_construction_project": "UI-SITE-PROJECT"}).insert(set_name="UI-SITE-WORKER")
    if not frappe.db.exists("Vehicle", "UI-SITE-TRUCK"):
        frappe.get_doc({"doctype": "Vehicle", "license_plate": "UI-SITE-TRUCK", "make": "Test", "model": "Truck",
            "last_odometer": 100, "fuel_type": "Diesel", "uom": "Litre", "company": company.name}).insert()
    if not frappe.db.exists("Project", "UI-MEALS-PROJECT"):
        frappe.get_doc({"doctype": "Project", "project_name": "Meals workflow test", "company": company.name,
            "cost_center": company.cost_center}).insert(set_name="UI-MEALS-PROJECT")
        category = frappe.db.get_value("Construction Cost Category", {"category_name": "Meals", "scope": "Global"}, "name")
        frappe.get_doc({"doctype": "Construction Cost Plan", "plan_name": "UI-MEALS-BUDGET",
            "project": "UI-MEALS-PROJECT", "version_kind": "Tender baseline", "items": [{"category": category,
                "account": company.default_expense_account, "original_estimate": 20000}]}).insert().submit()
    for number in (1, 2):
        employee = "UI-MEAL-WORKER-" + str(number)
        if not frappe.db.exists("Employee", employee):
            frappe.get_doc({"doctype": "Employee", "first_name": "UI Meal Worker " + str(number), "gender": "Male",
                "date_of_birth": "1990-01-01", "date_of_joining": add_days(nowdate(), -30), "company": company.name,
                "status": "Active", "custom_construction_project": "UI-MEALS-PROJECT"}).insert(set_name=employee)
        if not frappe.db.exists("Attendance", {"employee": employee, "attendance_date": nowdate(), "docstatus": 1}):
            frappe.get_doc({"doctype": "Attendance", "employee": employee, "attendance_date": nowdate(),
                "company": company.name, "status": "Present", "custom_construction_project": "UI-MEALS-PROJECT"}).insert().submit()
    frappe.db.commit()
