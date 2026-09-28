"""Permission-checked daily work, backed by normal ERPNext purchase invoices."""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import UUID

import frappe
from frappe import _
from frappe.utils import escape_html, flt, getdate, nowdate, strip_html


def home_page(user):
    if user != "Guest" and set(frappe.get_roles(user)) & {"System Manager", "Projects Manager"}:
        return "construction"


def require_manager():
    if frappe.session.user == "Guest" or not set(frappe.get_roles()) & {"System Manager", "Projects Manager"}:
        frappe.throw(_("You do not have access to the construction daily view."), frappe.PermissionError)


def checked_project(name):
    require_manager()
    project = frappe.get_doc("Project", name)
    project.check_permission("read")
    if not project.company:
        frappe.throw(_("Set a company for this project in setup first."))
    return project


def plan_for(project):
    baseline = frappe.get_list("Construction Cost Plan", filters={"project": project,
        "version_kind": "Tender baseline", "docstatus": 1}, pluck="name")
    if len(baseline) != 1:
        return None
    revisions = frappe.get_list("Construction Cost Plan", filters={"baseline": baseline[0],
        "version_kind": "Approved revision", "docstatus": 1, "status": "Approved"}, pluck="name")
    if len(revisions) > 1:
        frappe.throw(_("More than one budget revision is active. Review the project setup."))
    plan = frappe.get_doc("Construction Cost Plan", revisions[0] if revisions else baseline[0])
    plan.check_permission("read")
    return plan


def category_options(project):
    plan = plan_for(project.name)
    if not plan:
        return []
    options = []
    for row in plan.items:
        category = frappe.get_cached_doc("Construction Cost Category", row.category)
        account = frappe.get_cached_doc("Account", row.account)
        if (not category.disabled and (category.scope == "Global" or category.project == project.name)
                and account.company == project.company and account.root_type == "Expense"
                and not account.disabled and not account.is_group):
            options.append({"account": row.account, "category": row.category,
                "label": category.category_name, "detail": account.account_name,
                "entry_type": category.entry_type or "General", "scope": category.scope})
    return options


@frappe.whitelist()
def projects():
    require_manager()
    return {"today": nowdate(), "projects": frappe.get_list("Project",
        filters={"status": ["!=", "Cancelled"]}, fields=["name", "project_name", "status", "company"],
        order_by="modified desc", limit_page_length=100)}


@frappe.whitelist()
def overview(project):
    project = checked_project(project)
    currency = frappe.get_cached_value("Company", project.company, "default_currency")
    plan = plan_for(project.name)
    rows = []
    if plan:
        from hiru_construction.construction.report.construction_project_costs.construction_project_costs import execute
        rows = execute({"project": project.name})[1]
    recent = frappe.get_list("Purchase Invoice", filters={"project": project.name, "docstatus": ["<", 2],
        "custom_construction_entry_id": ["is", "set"]},
        fields=["name", "supplier_name", "posting_date", "grand_total", "currency", "docstatus"],
        order_by="creation desc", limit_page_length=20) if frappe.has_permission("Purchase Invoice", "read") else []
    categories = category_options(project)
    accounts = frappe.get_list("Account", filters={"company": project.company, "is_group": 0,
        "disabled": 0, "account_type": ["in", ["Cash", "Bank"]], "account_currency": currency},
        fields=["name", "account_name"], limit_page_length=100) if frappe.has_permission("Account", "read") else []
    grouped = {}
    for row in rows:
        category_id = next((item.category for item in plan.items if item.account == row["account"]), None)
        entry = grouped.setdefault(category_id, {"id": category_id, "label": row["category"], "budget": 0,
            "spent": 0, "orders": 0, "review_receipts": False})
        entry["budget"] += row["current_budget"]
        entry["spent"] += row["actual"]
        entry["orders"] += row["commitment"]
        entry["review_receipts"] |= bool(row["reconciliation"])
    tasks = frappe.get_list("Task", filters={"project": project.name, "status": ["not in", ["Cancelled", "Template"]]},
        fields=["name", "subject", "status", "exp_end_date"], order_by="exp_end_date asc", limit_page_length=100)
    return {"project": project.name, "title": project.project_name, "currency": currency,
        "has_budget": bool(plan), "budget": sum(r["current_budget"] for r in rows),
        "spent": sum(r["actual"] for r in rows), "orders": sum(r["commitment"] for r in rows),
        "remaining": None if any(r["reconciliation"] for r in rows) else sum(r["remaining_budget"] for r in rows),
        "groups": list(grouped.values()), "categories": categories, "payment_accounts": accounts,
        "recent": recent, "tasks": tasks, "can_create": bool(frappe.has_permission("Purchase Invoice", "create")),
        "can_add_supplier": bool(frappe.has_permission("Supplier", "create"))}


@frappe.whitelist()
def suppliers(search=""):
    require_manager()
    return frappe.get_list("Supplier", filters={"disabled": 0, "supplier_name": ["like", "%" + search[:80] + "%"]},
        fields=["name", "supplier_name"], order_by="supplier_name", limit_page_length=30)


@frappe.whitelist(methods=["POST"])
def add_supplier(name):
    require_manager()
    name = " ".join(str(name).split())
    if not name or len(name) > 140:
        frappe.throw(_("Enter a supplier name of up to 140 characters."))
    existing = frappe.get_list("Supplier", filters={"supplier_name": name, "disabled": 0},
        fields=["name", "supplier_name"], limit_page_length=1)
    if existing:
        return existing[0]
    doc = frappe.get_doc({"doctype": "Supplier", "supplier_name": name,
        "supplier_type": "Company", "supplier_group": "All Supplier Groups"}).insert()
    return {"name": doc.name, "supplier_name": doc.supplier_name}


def canonical(payload):
    payload = frappe.parse_json(payload) if isinstance(payload, str) else payload
    if not isinstance(payload, dict):
        frappe.throw(_("Expense details are required."))
    try:
        request_id = str(UUID(str(payload.get("request_id", ""))))
        amount = Decimal(str(payload.get("amount", "")))
        if not amount.is_finite() or amount <= 0 or amount > Decimal("99999999999.99") or amount != amount.quantize(Decimal("0.01")):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw(_("Enter a positive amount with at most two decimal places and retry."))
    data = {field: str(payload.get(field) or "").strip() for field in
        ("project", "account", "supplier", "description", "date", "paid_from", "bill_no",
         "vehicle", "machine", "litres", "meter", "meal")}
    if not all(data[f] for f in ("project", "account", "supplier", "description", "date")):
        frappe.throw(_("Choose a project, category and supplier, then enter a date and description."))
    if len(data["description"]) > 500 or len(data["bill_no"]) > 140:
        frappe.throw(_("Keep the description under 500 characters and receipt number under 140."))
    data["amount"] = str(amount.quantize(Decimal("0.01")))
    data["date"] = str(getdate(data["date"]))
    digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    return request_id, digest, data


def existing_request(request_id, digest):
    name = frappe.db.get_value("Purchase Invoice", {"custom_construction_entry_id": request_id}, "name")
    if not name:
        return None
    doc = frappe.get_doc("Purchase Invoice", name)
    doc.check_permission("read")
    checked_project(doc.project)
    if doc.custom_construction_request_hash != digest:
        frappe.throw(_("This expense was already saved with different details. Open its draft to review it."))
    return expense(name)


@frappe.whitelist(methods=["POST"])
def save_expense(payload):
    require_manager()
    request_id, digest, data = canonical(payload)
    project = checked_project(data["project"])
    if existing := existing_request(request_id, digest):
        return existing
    if getdate(data["date"]) > getdate():
        frappe.throw(_("An expense date cannot be in the future."))
    if project.status != "Open":
        frappe.throw(_("Only open projects can receive new expenses here."))
    mapping = next((row for row in category_options(project) if row["account"] == data["account"]), None)
    if not mapping:
        frappe.throw(_("This category is not available in the current project budget. Refresh and choose again."))
    if mapping["entry_type"] == "Fuel":
        from hiru_construction.fuel import number
        number(data["litres"], positive=True)
        if data["vehicle"] or data["meter"]:
            number(data["meter"])
    supplier = frappe.get_doc("Supplier", data["supplier"])
    supplier.check_permission("read")
    if supplier.disabled:
        frappe.throw(_("This supplier is disabled."))
    currency = frappe.get_cached_value("Company", project.company, "default_currency")
    if data["paid_from"]:
        account = frappe.get_doc("Account", data["paid_from"])
        account.check_permission("read")
        if (account.company != project.company or account.is_group or account.disabled
                or account.account_type not in ("Cash", "Bank") or account.account_currency != currency):
            frappe.throw(_("Choose an active cash or bank account in the project's currency."))
    cost_center = project.cost_center or frappe.get_cached_value("Company", project.company, "cost_center")
    amount = flt(data["amount"])
    invoice = frappe.get_doc({"doctype": "Purchase Invoice", "supplier": supplier.name,
        "company": project.company, "currency": currency, "conversion_rate": 1,
        "disable_rounded_total": 1,
        "project": project.name, "posting_date": data["date"], "set_posting_time": 1,
        "due_date": data["date"], "bill_date": data["date"], "bill_no": data["bill_no"],
        "remarks": data["description"],
        "custom_construction_entry_id": request_id, "custom_construction_request_hash": digest,
        "custom_construction_category": mapping["category"],
        "custom_construction_meal": data["meal"],
        "custom_construction_vehicle": data["vehicle"], "custom_construction_machine": data["machine"],
        "custom_construction_litres": data["litres"] or 0, "custom_construction_meter": data["meter"] or 0,
        "custom_construction_meter_recorded": bool(data["meter"]),
        "is_paid": bool(data["paid_from"]), "cash_bank_account": data["paid_from"],
        "paid_amount": amount if data["paid_from"] else 0,
        "items": [{"item_name": data["description"][:140], "description": escape_html(data["description"]),
            "qty": 1, "uom": "Nos", "rate": amount, "expense_account": mapping["account"],
            "cost_center": cost_center, "project": project.name}],
    })
    try:
        invoice.insert()
    except (frappe.DuplicateEntryError, frappe.UniqueValidationError):
        frappe.db.rollback()
        if existing := existing_request(request_id, digest):
            return existing
        raise
    # Never silently add default supplier taxes or alter the entered total.
    if invoice.taxes or flt(invoice.grand_total, 2) != amount:
        frappe.throw(_("This supplier needs a tax breakdown. Please use advanced expense entry."))
    return expense(invoice.name)


@frappe.whitelist()
def expense(name):
    require_manager()
    doc = frappe.get_doc("Purchase Invoice", name)
    doc.check_permission("read")
    checked_project(doc.project)
    if not doc.custom_construction_entry_id:
        frappe.throw(_("Open this bill in the advanced accounts view."))
    files = frappe.get_list("File", filters={"attached_to_doctype": "Purchase Invoice", "attached_to_name": doc.name},
        fields=["file_name", "file_url"], limit_page_length=20)
    meal_info = None
    if doc.custom_construction_meal:
        from hiru_construction.meals import checked_meal, summary
        meal_info = summary(checked_meal(doc.custom_construction_meal))
    return {"name": doc.name, "modified": str(doc.modified), "docstatus": doc.docstatus,
        "project": doc.project, "supplier": doc.supplier_name, "amount": doc.grand_total,
        "currency": doc.currency, "date": str(doc.posting_date), "bill_no": doc.bill_no,
        "category": frappe.get_cached_value("Construction Cost Category", doc.custom_construction_category, "category_name"),
        "description": " / ".join(strip_html(row.description or row.item_name or "") for row in doc.items),
        "payment": frappe.get_cached_value("Account", doc.cash_bank_account, "account_name") if doc.is_paid else None,
        "meal": doc.custom_construction_meal, "meal_info": meal_info,
        "vehicle": doc.custom_construction_vehicle, "machine": doc.custom_construction_machine,
        "litres": doc.custom_construction_litres, "meter": doc.custom_construction_meter if doc.custom_construction_meter_recorded else None,
        "files": files, "can_submit": bool(doc.has_permission("submit"))}


@frappe.whitelist(methods=["POST"])
def post_expense(name, modified):
    require_manager()
    frappe.db.sql("select name from `tabPurchase Invoice` where name=%s for update", name)
    doc = frappe.get_doc("Purchase Invoice", name)
    doc.check_permission("submit")
    checked_project(doc.project)
    if not doc.custom_construction_entry_id:
        frappe.throw(_("This bill must be reviewed in the advanced accounts view."))
    if doc.docstatus == 1:
        return expense(name)
    if doc.docstatus != 0:
        frappe.throw(_("This expense has been cancelled."))
    if str(doc.modified) != modified:
        frappe.throw(_("This draft has changed. Close and reopen it to review the latest details."))
    if len(doc.items) != 1 or doc.taxes or doc.update_stock or doc.is_return or not doc.disable_rounded_total:
        frappe.throw(_("This bill now needs advanced review before it can be recorded."))
    doc.submit()
    return expense(name)
