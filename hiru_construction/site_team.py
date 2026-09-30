"""Supervisor submissions and cash custody, with owner-reviewed native vouchers.

The wallet is a real company cash account. Pending spending is shown separately
until its invoice is approved. Funding transfers never become project expenses.
"""
import hashlib
import json
from decimal import Decimal, InvalidOperation
from uuid import UUID

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, now_datetime

from hiru_construction.site_access import is_owner, require_owner, require_site_user, wallet_access, service_write
from hiru_construction.site_work import hours, work_date


def save(doc):
    with service_write():
        if doc.is_new():
            doc.insert(ignore_permissions=True)
        else:
            doc.save(ignore_permissions=True)
    return doc


def reason(value):
    value = str(value or "").strip()
    if not value or len(value) > 500:
        frappe.throw(_("Enter a reason of up to 500 characters."))
    return value


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0 or amount > 99999999 or amount != amount.quantize(Decimal(".01")):
            raise ValueError
        return float(amount)
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw(_("Enter a positive amount with at most two decimal places."))


def signature(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def retry(key, digest, wallet):
    try:
        key = str(UUID(str(key)))
    except ValueError:
        frappe.throw(_("Reload the form and try again."))
    name = frappe.db.get_value("Construction Site Entry", {"request_key": key}, "name")
    if name:
        doc = frappe.get_doc("Construction Site Entry", name)
        if doc.wallet != wallet or doc.request_hash != digest:
            frappe.throw(_("This request was already used with different details."))
        return doc


def project_for(wallet):
    project = frappe.get_doc("Project", wallet.project)
    if project.status != "Open":
        frappe.throw(_("New entries require an open project."))
    return project


def categories(project):
    # Explicitly scoped portal projection: no budget, payroll or ledger amounts.
    baselines = frappe.get_all("Construction Cost Plan", filters={"project": project, "docstatus": 1,
        "version_kind": "Tender baseline"}, pluck="name")
    if len(baselines) != 1:
        return []
    revisions = frappe.get_all("Construction Cost Plan", filters={"baseline": baselines[0],
        "docstatus": 1, "status": "Approved", "version_kind": "Approved revision"}, pluck="name")
    if len(revisions) > 1:
        frappe.throw(_("The owner must resolve multiple active budgets."))
    plan = frappe.get_doc("Construction Cost Plan", revisions[0] if revisions else baselines[0])
    result = []
    for row in plan.items:
        category = frappe.get_cached_doc("Construction Cost Category", row.category)
        if not category.disabled and (category.scope == "Global" or category.project == project):
            result.append({"value": row.category, "label": category.category_name,
                "entry_type": category.entry_type or "General", "account": row.account})
    return result


@frappe.whitelist(methods=["POST"])
def create_user(email, full_name, password, access="Supervisor"):
    require_owner()
    if access not in ("Owner", "Supervisor"):
        frappe.throw(_("Choose Owner or Supervisor."))
    if not password or len(password) < 12:
        frappe.throw(_("Use an initial password of at least 12 characters."))
    roles = ["Construction Supervisor"] if access == "Supervisor" else [
        "System Manager", "Accounts Manager", "Accounts User", "Projects Manager", "HR Manager", "HR User",
        "Payroll Manager", "Payroll User", "Stock Manager", "Stock User", "Purchase Manager", "Purchase User", "Sales Manager"]
    user = frappe.get_doc({"doctype": "User", "email": email, "first_name": reason(full_name),
        "enabled": 1, "user_type": "Website User" if access == "Supervisor" else "System User",
        "send_welcome_email": 0, "new_password": password,
        "roles": [{"role": role} for role in roles if frappe.db.exists("Role", role)]}).insert()
    return {"user": user.name}


@frappe.whitelist(methods=["POST"])
def add_supervisor(project, supervisor=None, email=None, full_name=None, password=None):
    """Create a restricted login and its assignment in the same request transaction."""
    require_owner()
    from hiru_construction.daily import checked_project
    project = checked_project(project)
    if project.status != "Open":
        frappe.throw(_("Choose an open project when giving a supervisor access."))
    if not supervisor:
        if frappe.db.exists("User", str(email or "").strip().lower()):
            frappe.throw(_("This login already exists. Choose Existing supervisor to give them access."))
        supervisor = create_user(email, full_name, password, access="Supervisor")["user"]
    result = assign(project.name, supervisor)
    set_enabled(result["wallet"], 1)
    return {**result, "user": supervisor}


@frappe.whitelist(methods=["POST"])
def assign(project, supervisor):
    require_owner()
    from hiru_construction.daily import checked_project
    project = checked_project(project)
    user = frappe.get_doc("User", supervisor)
    if not user.enabled or "Construction Supervisor" not in frappe.get_roles(user.name) or is_owner(user.name):
        frappe.throw(_("Choose an enabled supervisor account."))
    # A portal supervisor must not also have roles granting accounting or HR access.
    if set(frappe.get_roles(user.name)) - {"Construction Supervisor", "All", "Guest"}:
        frappe.throw(_("Remove other roles from this supervisor before assigning a site."))
    frappe.db.sql("select name from `tabProject` where name=%s for update", project.name)
    key = signature([project.name, user.name])
    existing = frappe.db.get_value("Construction Site Wallet", {"assignment_key": key}, "name")
    if existing:
        return {"wallet": existing}
    parents = frappe.get_all("Account", filters={"company": project.company, "is_group": 1,
        "account_type": "Cash"}, pluck="name", limit_page_length=1)
    if not parents:
        frappe.throw(_("Create a Cash group in this company's chart of accounts first."))
    account = frappe.get_doc({"doctype": "Account", "account_name": "Site cash " + key[:12],
        "company": project.company, "parent_account": parents[0], "account_type": "Cash",
        "account_currency": frappe.get_cached_value("Company", project.company, "default_currency")}).insert()
    doc = save(frappe.get_doc({"doctype": "Construction Site Wallet", "project": project.name,
        "supervisor": user.name, "account": account.name, "enabled": 1, "assignment_key": key}))
    return {"wallet": doc.name}


@frappe.whitelist(methods=["POST"])
def set_enabled(wallet, enabled):
    require_owner()
    doc = wallet_access(wallet, lock=True, active=False)
    doc.enabled = 1 if str(enabled) in ("1", "true", "True") else 0
    save(doc)
    return {"enabled": doc.enabled}


@frappe.whitelist()
def bootstrap():
    require_site_user()
    filters = {} if is_owner() else {"supervisor": frappe.session.user, "enabled": 1}
    wallets = frappe.get_all("Construction Site Wallet", filters=filters,
        fields=["name", "project", "supervisor", "enabled"], order_by="creation asc", limit_page_length=0)
    for row in wallets:
        row["project_name"] = frappe.get_cached_value("Project", row.project, "project_name")
        row["supervisor_name"] = frappe.get_cached_value("User", row.supervisor, "full_name")
    data = {"owner": is_owner(), "today": nowdate(), "wallets": wallets}
    if is_owner():
        data["projects"] = frappe.get_list("Project", fields=["name", "project_name", "status"],
            order_by="project_name asc", limit_page_length=0)
        names = frappe.get_all("Has Role", filters={"role": "Construction Supervisor", "parenttype": "User"}, pluck="parent")
        data["supervisors"] = frappe.get_all("User", filters={"name": ["in", names], "enabled": 1},
            fields=["name", "full_name"], limit_page_length=0) if names else []
    return data


def balance(wallet):
    posted = Decimal(str(frappe.db.sql("""select coalesce(sum(debit-credit),0) from `tabGL Entry`
        where account=%s and is_cancelled=0 and voucher_type!='Period Closing Voucher'""", wallet.account)[0][0]))
    # Replacement proposals do not supersede the original until owner approval.
    pending = sum((Decimal(str(row.amount)) for row in frappe.get_all("Construction Site Entry",
        filters={"wallet": wallet.name, "kind": "Expense", "state": "Pending", "revision_of": ["is", "not set"]},
        fields=["amount"], limit_page_length=0)), Decimal(0))
    return {"posted": float(posted), "pending": float(pending), "reported": float(posted - pending)}


@frappe.whitelist()
def details(wallet):
    wallet = wallet_access(wallet, active=False)
    project = frappe.get_doc("Project", wallet.project)
    records = frappe.get_all("Construction Site Entry", filters={"wallet": wallet.name},
        fields=["name", "kind", "entry_date", "amount", "description", "state", "payload", "revision_of", "voucher_type", "voucher",
                "correction_state", "correction_reason", "review_reason", "reviewed_by", "granted_by", "replacement", "owner"],
        order_by="creation desc", limit_page_length=0)
    result = {"wallet": wallet.name, "enabled": wallet.enabled, "project": wallet.project, "records": records,
        "currency": frappe.get_cached_value("Company", project.company, "default_currency"), **balance(wallet),
        "categories": [{k: v for k, v in row.items() if k != "account"} for row in categories(wallet.project)],
        "workers": frappe.get_all("Employee", filters={"company": project.company, "custom_construction_project": wallet.project, "status": "Active"}, fields=["name", "employee_name"], limit_page_length=0),
        "suppliers": frappe.get_all("Supplier", filters={"disabled": 0}, fields=["name", "supplier_name"], limit_page_length=0),
        "vehicles": frappe.get_all("Vehicle", filters={"company": project.company}, fields=["name"], limit_page_length=0),
        "machines": frappe.get_all("Asset", filters={"company": project.company, "docstatus": 1}, fields=["name", "asset_name"], limit_page_length=0),
        "meals": frappe.get_all("Construction Meal", filters={"project": project.name}, fields=["name", "meal_label", "meal_date"], limit_page_length=0)}
    if is_owner():
        custody = frappe.get_all("Construction Site Wallet", pluck="account", limit_page_length=0)
        result["cash_accounts"] = frappe.get_list("Account", filters={"company": project.company, "is_group": 0,
            "disabled": 0, "account_type": ["in", ["Cash", "Bank"]], "account_currency": result["currency"],
            "name": ["not in", custody]}, fields=["name", "account_name"], limit_page_length=0)
    return result


def validate_payload(wallet, kind, payload):
    payload = frappe.parse_json(payload)
    if not isinstance(payload, dict):
        frappe.throw(_("Entry details are required."))
    project = project_for(wallet)
    data = {"date": str(work_date(payload.get("date")))}
    if kind == "Expense":
        data.update({key: str(payload.get(key) or "").strip() for key in
            ("category", "supplier", "description", "bill_no", "vehicle", "machine", "litres", "meter", "meal")})
        data["description"] = reason(data["description"])
        data["amount"] = money(payload.get("amount"))
        category = next((row for row in categories(project.name) if row["value"] == data["category"]), None)
        if not category or not frappe.db.exists("Supplier", {"name": data["supplier"], "disabled": 0}):
            frappe.throw(_("Choose an available project category and supplier."))
        if category["entry_type"] == "Fuel":
            from hiru_construction.fuel import number
            if bool(data["vehicle"]) == bool(data["machine"]):
                frappe.throw(_("Select one vehicle or machine for fuel."))
            equipment_type, equipment = ("Vehicle", data["vehicle"]) if data["vehicle"] else ("Asset", data["machine"])
            if not frappe.db.exists(equipment_type, {"name": equipment, "company": project.company}):
                frappe.throw(_("Choose equipment from this company."))
            number(data["litres"], positive=True)
            if data["vehicle"] or data["meter"]:
                if not data["meter"]:
                    frappe.throw(_("Enter the odometer reading."))
                number(data["meter"])
        elif any(data[k] for k in ("vehicle", "machine", "litres", "meter")):
            frappe.throw(_("Equipment details are only used for fuel expenses."))
        if category["entry_type"] == "Meals":
            if not frappe.db.exists("Construction Meal", {"name": data["meal"], "project": project.name, "meal_date": data["date"]}):
                frappe.throw(_("Ask the owner to set up this day's meal, then choose it here."))
        elif data["meal"]:
            frappe.throw(_("Only Meals expenses can link a meal."))
        if len(data["bill_no"]) > 140:
            frappe.throw(_("Receipt number must be at most 140 characters."))
    elif kind == "Attendance":
        data.update({"employee": payload.get("employee"), "status": payload.get("status"),
            "regular": hours(payload.get("regular")), "ot": hours(payload.get("ot"))})
        if not frappe.db.exists("Employee", {"name": data["employee"], "company": project.company,
                "custom_construction_project": project.name, "status": "Active"}):
            frappe.throw(_("Choose an active worker assigned to this project."))
        if data["status"] not in ("Present", "Absent", "Half Day") or data["regular"] + data["ot"] > 24:
            frappe.throw(_("Choose a valid attendance status and up to 24 total hours."))
        if (data["status"] == "Absent" and (data["regular"] or data["ot"])) or (data["status"] != "Absent" and data["regular"] <= 0):
            frappe.throw(_("Absent workers have zero hours; present workers need regular hours."))
    else:
        frappe.throw(_("Choose Expense or Attendance."))
    return data


@frappe.whitelist(methods=["POST"])
def submit_entry(wallet, kind, payload, request_key, revision_of=None):
    wallet = wallet_access(wallet, lock=True)
    data = validate_payload(wallet, kind, payload)
    digest = signature([kind, data, revision_of or ""])
    if existing := retry(request_key, digest, wallet.name):
        return {"name": existing.name}
    original = None
    if revision_of:
        original = frappe.get_doc("Construction Site Entry", revision_of)
        if (original.wallet != wallet.name or original.kind != kind or original.state not in ("Pending", "Approved")
                or original.correction_state != "Granted" or (original.revision_of and original.state == "Pending")):
            frappe.throw(_("The owner must grant a correction for this specific entry first."), frappe.PermissionError)
        if kind == "Attendance":
            old = frappe.parse_json(original.payload)
            if any(old[key] != data[key] for key in ("employee", "date")):
                frappe.throw(_("An attendance correction keeps its worker and date."))
    if kind == "Attendance":
        frappe.db.sql("select name from `tabEmployee` where name=%s for update", data["employee"])
        # Prevent concurrent supervisors from creating duplicate marks for the same worker/day.
        candidates = frappe.get_all("Construction Site Entry", filters={"kind": kind, "entry_date": data["date"],
            "state": ["in", ["Pending", "Approved"]]}, fields=["name", "payload", "revision_of"], limit_page_length=0)
        for row in candidates:
            if frappe.parse_json(row.payload).get("employee") == data["employee"] and row.name != revision_of:
                frappe.throw(_("This worker already has a submitted mark for this day. Request a correction."))
        if not original and frappe.db.exists("Attendance", {"employee": data["employee"], "attendance_date": data["date"], "docstatus": ["<", 2]}):
            frappe.throw(_("Attendance already exists for this worker and date."))
    doc = save(frappe.get_doc({"doctype": "Construction Site Entry", "wallet": wallet.name, "kind": kind,
        "entry_date": data["date"], "amount": data.get("amount", 0), "description": data.get("description") or
            f"{frappe.get_cached_value('Employee', data['employee'], 'employee_name')} · {data['status']} · {data['regular']} regular + {data['ot']} OT hours",
        "payload": json.dumps(data), "request_key": request_key, "request_hash": digest,
        "revision_of": revision_of, "state": "Pending"}))
    if original:
        original.correction_state = "Used"
        original.replacement = doc.name
        save(original)
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def submit_crew(wallet, date, rows):
    wallet_access(wallet, lock=True)
    rows = frappe.parse_json(rows)
    if not isinstance(rows, list) or not rows or len(rows) > 100:
        frappe.throw(_("Select between 1 and 100 workers."))
    if len({row.get("employee") for row in rows}) != len(rows):
        frappe.throw(_("Each worker must appear only once."))
    result = []
    for row in sorted(rows, key=lambda row: row["employee"]):
        result.append(submit_entry(wallet, "Attendance", {**row, "date": date}, row.get("request_key")))
    return {"saved": len(result)}


def locked_entry(name):
    wallet = frappe.db.get_value("Construction Site Entry", name, "wallet")
    wallet = wallet_access(wallet, lock=True, active=False)
    return wallet, frappe.get_doc("Construction Site Entry", name)


@frappe.whitelist(methods=["POST"])
def request_correction(name, explanation):
    wallet, doc = locked_entry(name)
    if not wallet.enabled and not is_owner():
        frappe.throw(_("This assignment is disabled."), frappe.PermissionError)
    if doc.kind not in ("Expense", "Attendance") or doc.state not in ("Pending", "Approved") or doc.correction_state in ("Requested", "Granted", "Used"):
        frappe.throw(_("This entry cannot receive another correction request."))
    if doc.revision_of and doc.state == "Pending":
        frappe.throw(_("The owner must review this correction before it can be corrected again."))
    doc.correction_state, doc.correction_reason = "Requested", reason(explanation)
    save(doc)
    return {"state": "Requested"}


@frappe.whitelist(methods=["POST"])
def grant_correction(name):
    require_owner()
    _, doc = locked_entry(name)
    if doc.correction_state == "Granted":
        return {"state": "Granted"}
    if doc.correction_state != "Requested" or doc.state not in ("Pending", "Approved"):
        frappe.throw(_("A current correction request is required."))
    doc.correction_state, doc.granted_by, doc.granted_on = "Granted", frappe.session.user, now_datetime()
    save(doc)
    return {"state": "Granted"}


@frappe.whitelist(methods=["POST"])
def review(name, decision, explanation):
    require_owner()
    wallet, doc = locked_entry(name)
    target = {"Approve": "Approved", "Reject": "Rejected"}.get(decision)
    if target is None:
        frappe.throw(_("Choose Approve or Reject."))
    if doc.state == target:
        return {"state": doc.state}
    if doc.state != "Pending":
        frappe.throw(_("This entry has already been reviewed."))
    doc.review_reason = reason(explanation)
    original = frappe.get_doc("Construction Site Entry", doc.revision_of) if doc.revision_of else None
    with service_write():
        if decision == "Approve":
            data = validate_payload(wallet, doc.kind, doc.payload)
            if original:
                if original.replacement != doc.name or original.state not in ("Pending", "Approved"):
                    frappe.throw(_("The original entry changed. Review its current state."))
                if original.state == "Approved":
                    frappe.get_doc(original.voucher_type, original.voucher).cancel()
                original.state = "Superseded"
                save(original)
            if doc.kind == "Expense":
                from hiru_construction.daily import save_expense, post_expense
                category = next(row for row in categories(wallet.project) if row["value"] == data["category"])
                draft = save_expense({**data, "request_id": doc.request_key, "project": wallet.project,
                    "account": category["account"], "paid_from": wallet.account})
                posted = post_expense(draft["name"], draft["modified"])
                doc.voucher_type, doc.voucher = "Purchase Invoice", posted["name"]
            else:
                from hiru_construction.site_work import save_attendance
                save_attendance(wallet.project, data["date"], [data], confirm=True)
                doc.voucher_type = "Attendance"
                doc.voucher = frappe.db.get_value("Attendance", {"employee": data["employee"], "attendance_date": data["date"], "docstatus": 1}, "name")
        elif original:
            # A rejected proposal does not change the effective original; a fresh grant is needed.
            original.correction_state, original.replacement = "", None
            save(original)
        doc.state, doc.reviewed_by, doc.reviewed_on = target, frappe.session.user, now_datetime()
        save(doc)
    return {"state": doc.state, "voucher": doc.voucher}


@frappe.whitelist(methods=["POST"])
def transfer(wallet, kind, amount, date, account, explanation, request_key):
    require_owner()
    wallet = wallet_access(wallet, lock=True, active=False)
    # Outstanding funds can still be settled after a site closes or access is revoked.
    project = frappe.get_doc("Project", wallet.project)
    amount, date, explanation = money(amount), str(work_date(date)), reason(explanation)
    if kind not in ("Funding", "Return"):
        frappe.throw(_("Choose money given or money returned."))
    source = frappe.get_doc("Account", account)
    currency = frappe.get_cached_value("Company", project.company, "default_currency")
    if (source.company != project.company or source.is_group or source.disabled or source.account_type not in ("Cash", "Bank")
            or source.account_currency != currency or frappe.db.exists("Construction Site Wallet", {"account": source.name})):
        frappe.throw(_("Choose a company cash or bank account outside supervisor wallets."))
    data = {"kind": kind, "amount": amount, "date": date, "account": account, "explanation": explanation}
    digest = signature(data)
    if existing := retry(request_key, digest, wallet.name):
        return {"name": existing.name}
    debit, credit = (wallet.account, account) if kind == "Funding" else (account, wallet.account)
    journal = frappe.get_doc({"doctype": "Journal Entry", "company": project.company,
        "voucher_type": "Journal Entry", "posting_date": date, "user_remark": explanation,
        "accounts": [{"account": debit, "debit_in_account_currency": amount, "project": project.name},
                     {"account": credit, "credit_in_account_currency": amount, "project": project.name}]}).insert()
    journal.submit()
    doc = save(frappe.get_doc({"doctype": "Construction Site Entry", "wallet": wallet.name, "kind": kind,
        "entry_date": date, "amount": amount, "description": explanation, "payload": json.dumps(data),
        "request_key": request_key, "request_hash": digest, "state": "Approved", "voucher_type": "Journal Entry",
        "voucher": journal.name, "reviewed_by": frappe.session.user, "reviewed_on": now_datetime()}))
    return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def reverse_transfer(name, explanation):
    require_owner()
    _, doc = locked_entry(name)
    if doc.kind not in ("Funding", "Return") or doc.state != "Approved":
        frappe.throw(_("Only an approved cash transfer can be reversed here."))
    explanation = reason(explanation)
    with service_write():
        frappe.get_doc(doc.voucher_type, doc.voucher).cancel()
        doc.state, doc.review_reason = "Rejected", explanation
        doc.reviewed_by, doc.reviewed_on = frappe.session.user, now_datetime()
        save(doc)
    return {"state": doc.state}


@frappe.whitelist(methods=["POST"])
def void_entry(name, explanation):
    require_owner()
    _, doc = locked_entry(name)
    if doc.kind not in ("Expense", "Attendance") or doc.state != "Approved":
        frappe.throw(_("Only an approved expense or attendance entry can be voided."))
    if doc.replacement and frappe.db.get_value("Construction Site Entry", doc.replacement, "state") == "Pending":
        frappe.throw(_("Reject the pending correction before voiding its original entry."))
    explanation = reason(explanation)
    with service_write():
        frappe.get_doc(doc.voucher_type, doc.voucher).cancel()
        doc.state, doc.review_reason = "Rejected", "Voided: " + explanation
        doc.reviewed_by, doc.reviewed_on = frappe.session.user, now_datetime()
        save(doc)
    return {"state": doc.state}


@frappe.whitelist(methods=["POST"])
def decline_correction(name, explanation):
    require_owner()
    _, doc = locked_entry(name)
    if doc.correction_state not in ("Requested", "Granted"):
        frappe.throw(_("Only an unused correction request or grant can be declined."))
    doc.correction_reason = (doc.correction_reason or "") + "\nOwner declined/revoked: " + reason(explanation)
    doc.correction_state, doc.granted_by, doc.granted_on = "", None, None
    save(doc)
    return {"state": "Declined"}
