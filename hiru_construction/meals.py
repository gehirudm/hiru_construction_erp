"""Meal headcounts and limits; costs remain in standard Purchase Invoices."""
import hashlib
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, flt

from hiru_construction.daily import checked_project, category_options

TYPES = ("Breakfast", "Lunch", "Dinner")


def validate_rates(doc, method=None):
    seen = set()
    for row in doc.get("custom_construction_meal_rates") or []:
        if row.meal_type not in TYPES or row.meal_type in seen:
            frappe.throw(_("Use each meal type once in expected meal costs."))
        row.expected_per_head = positive_amount(row.expected_per_head)
        seen.add(row.meal_type)


def positive_amount(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount > 99999999 or amount != amount.quantize(Decimal(".01")):
            raise ValueError
        return float(amount)
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw(_("Enter a positive expected cost with at most two decimal places."))


def diner_count(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0 or number > 10000 or number != int(number):
            raise ValueError
        return int(number)
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw(_("Enter the actual number of diners, from 1 to 10,000."))


def attendance_count(project, date):
    employees = frappe.get_list("Attendance", filters={"custom_construction_project": project,
        "attendance_date": getdate(date), "docstatus": 1, "status": ["in", ["Present", "Half Day"]]},
        pluck="employee", limit_page_length=10000)
    return len(set(employees))


def summary(doc, locking=False):
    # Locking reads see preceding committed bills even after waiting for a meal lock.
    bills = frappe.db.sql("""select name, grand_total from `tabPurchase Invoice`
        where custom_construction_meal=%s and docstatus=1""" + (" for update" if locking else ""), doc.name, as_dict=True)
    total = sum(Decimal(str(b.grand_total)) for b in bills)
    allowance = Decimal(str(doc.expected_per_head)) * doc.diners
    return {"name": doc.name, "modified": str(doc.modified), "date": str(doc.meal_date),
        "type": doc.meal_type, "attendance_headcount": doc.attendance_headcount, "diners": doc.diners,
        "reason": doc.adjustment_reason, "expected": doc.expected_per_head, "currency": doc.currency,
        "total": float(total), "per_head": float(total / doc.diners) if doc.diners else None,
        "over_limit": total > allowance, "excess": float(max(Decimal(0), total - allowance)),
        "bill_count": len(bills)}


def checked_meal(name):
    doc = frappe.get_doc("Construction Meal", name)
    checked_project(doc.project)
    doc.check_permission("read")
    return doc


@frappe.whitelist()
def alerts(project):
    project = checked_project(project)
    return frappe.get_list("Construction Meal", filters={"project": project.name, "over_limit": 1},
        fields=["name", "meal_type", "meal_date"], order_by="meal_date desc", limit_page_length=50)


@frappe.whitelist()
def board(project, date=None):
    project = checked_project(project)
    date = getdate(date or nowdate())
    if date > getdate():
        frappe.throw(_("Choose today or an earlier date."))
    meals = frappe.get_list("Construction Meal", filters={"project": project.name, "meal_date": date},
        pluck="name", limit_page_length=10)
    recent = frappe.get_list("Construction Meal", filters={"project": project.name},
        pluck="name", order_by="meal_date desc, creation desc", limit_page_length=30)
    return {"date": str(date), "suggested_diners": attendance_count(project.name, date),
        "rates": {row.meal_type: row.expected_per_head for row in project.custom_construction_meal_rates},
        "meals": [summary(checked_meal(name)) for name in meals],
        "recent": [summary(checked_meal(name)) for name in recent],
        "categories": [row for row in category_options(project) if row["entry_type"] == "Meals"],
        "can_create": bool(frappe.has_permission("Construction Meal", "create")),
        "can_settings": bool(project.has_permission("write"))}


@frappe.whitelist(methods=["POST"])
def save_rates(project, rates):
    project = checked_project(project)
    project.check_permission("write")
    rates = frappe.parse_json(rates)
    if not isinstance(rates, dict) or not rates or any(key not in TYPES for key in rates):
        frappe.throw(_("Enter expected costs for breakfast, lunch or dinner."))
    # Allow partial configuration; each recorded meal needs its own configured rate.
    project.set("custom_construction_meal_rates", [
        {"meal_type": key, "expected_per_head": positive_amount(value)} for key, value in rates.items()])
    project.save()
    return {"saved": True}


@frappe.whitelist(methods=["POST"])
def save_meal(project, date, meal_type, diners, reason="", name=None, modified=None):
    project = checked_project(project)
    if project.status != "Open":
        frappe.throw(_("Meal entry requires an open project."))
    if not date or getdate(date) > getdate() or meal_type not in TYPES:
        frappe.throw(_("Choose a valid meal type and a date no later than today."))
    diners = diner_count(diners)
    frappe.db.sql("select name from `tabProject` where name=%s for update", project.name)
    existing = frappe.db.get_value("Construction Meal", {"project": project.name, "meal_date": date, "meal_type": meal_type}, "name")
    if existing:
        frappe.db.sql("select name from `tabConstruction Meal` where name=%s for update", existing)
        doc = checked_meal(existing)
        if doc.diners == diners and (doc.adjustment_reason or "") == reason:
            return summary(doc)
        if name != doc.name or str(doc.modified) != str(modified):
            frappe.throw(_("This meal already exists or changed. Reload it before adjusting the headcount."))
        doc.check_permission("write")
        doc.diners, doc.adjustment_reason = diners, reason
        doc.save()
    else:
        rate = next((row.expected_per_head for row in project.custom_construction_meal_rates if row.meal_type == meal_type), None)
        if not rate:
            frappe.throw(_("Set the expected cost per person for this meal first."))
        doc = frappe.get_doc({"doctype": "Construction Meal", "project": project.name, "meal_date": date,
            "meal_type": meal_type, "diners": diners, "adjustment_reason": reason, "expected_per_head": rate}).insert()
    return summary(doc)


def validate_invoice(doc, method=None):
    meal_name = doc.get("custom_construction_meal")
    kind = frappe.db.get_value("Construction Cost Category", doc.get("custom_construction_category"), "entry_type") if doc.get("custom_construction_entry_id") else None
    if not meal_name and kind != "Meals":
        return
    if not meal_name or kind != "Meals" or not doc.custom_construction_entry_id:
        frappe.throw(_("Record a Meals expense against a saved meal in the daily view."))
    frappe.db.sql("select name from `tabConstruction Meal` where name=%s for update", meal_name)
    meal = checked_meal(meal_name)
    project = checked_project(meal.project)
    if doc.project != meal.project or doc.company != project.company or getdate(doc.posting_date) != getdate(meal.meal_date):
        frappe.throw(_("The expense project and date must match the meal."))
    accounts = [row["account"] for row in category_options(project) if row["category"] == doc.custom_construction_category]
    if (len(doc.items) != 1 or doc.taxes or doc.update_stock or doc.is_return or not doc.disable_rounded_total
            or doc.currency != meal.currency or doc.items[0].project != meal.project
            or doc.items[0].expense_account not in accounts or doc.grand_total <= 0):
        frappe.throw(_("Meal costs need a simple project expense in the meal's currency and budget category."))


def invoice_changed(doc, method=None):
    if doc.get("custom_construction_meal"):
        update_alert(doc.custom_construction_meal)


def update_alert(name):
    frappe.db.sql("select name from `tabConstruction Meal` where name=%s for update", name)
    doc = frappe.get_doc("Construction Meal", name)
    data = summary(doc, locking=True)
    fingerprint = hashlib.sha256(f"{data['total']}|{doc.diners}|{doc.expected_per_head}".encode()).hexdigest() if data["over_limit"] else ""
    if fingerprint and fingerprint != doc.last_alert:
        # Notify the meal creator inside ERPNext only; never send email or external messages.
        frappe.get_doc({"doctype": "Notification Log", "for_user": doc.owner,
            "from_user": frappe.session.user, "type": "Construction Meal Alert", "document_type": doc.doctype,
            "document_name": doc.name,
            "subject": f"Meal budget exceeded: {doc.meal_type} on {doc.meal_date}",
            "email_content": f"{doc.currency} {flt(data['per_head'], 2)} per person; expected {flt(doc.expected_per_head, 2)}."}).insert(ignore_permissions=True)
    if (doc.last_alert or "") != fingerprint:
        frappe.db.set_value(doc.doctype, doc.name, "last_alert", fingerprint, update_modified=False)
    frappe.db.set_value(doc.doctype, doc.name, "over_limit", int(data["over_limit"]), update_modified=False)
