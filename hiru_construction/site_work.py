"""Small site workflows over standard Employee, Attendance and ledger records."""
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate, strip_html

from hiru_construction.daily import checked_project, plan_for


def hours(value):
    try:
        result = Decimal(str(value or 0))
        if not result.is_finite() or result < 0 or result > 24 or result != result.quantize(Decimal(".01")):
            raise ValueError
        return float(result)
    except (InvalidOperation, ValueError):
        frappe.throw(_("Hours must be between 0 and 24, with at most two decimal places."))


def work_date(value):
    if not value or getdate(value) > getdate():
        frappe.throw(_("Choose today or an earlier date."))
    return getdate(value)


@frappe.whitelist()
def crew(project, date=None):
    project = checked_project(project)
    date = work_date(date or nowdate())
    employees = frappe.get_list("Employee", filters={"company": project.company, "status": "Active",
        "custom_construction_project": project.name}, fields=["name", "employee_name"],
        order_by="employee_name", limit_page_length=500)
    names = [e.name for e in employees]
    records = frappe.get_list("Attendance", filters={"employee": ["in", names], "attendance_date": date,
        "docstatus": ["<", 2]}, fields=["name", "employee", "status", "docstatus", "modified",
        "custom_construction_project", "custom_construction_regular_hours", "actual_overtime_duration",
        "overtime_type", "standard_working_hours"], limit_page_length=1000) if names else []
    for employee in employees:
        matches = [r for r in records if r.employee == employee.name]
        employee["attendance"] = matches[0] if len(matches) == 1 else None
        employee["conflict"] = len(matches) > 1 or bool(matches and matches[0].custom_construction_project != project.name)
    week = frappe.get_list("Attendance", filters={"custom_construction_project": project.name,
        "attendance_date": ["between", [add_days(date, -6), date]], "docstatus": 1},
        fields=["custom_construction_regular_hours", "actual_overtime_duration"], limit_page_length=5000)
    return {"date": str(date), "employees": employees,
        "regular_total": sum(r.custom_construction_regular_hours or 0 for r in week),
        "ot_total": sum(r.actual_overtime_duration or 0 for r in week),
        "overtime_types": frappe.get_list("Overtime Type", pluck="name", limit_page_length=100)
            if frappe.has_permission("Overtime Type", "read") else [],
        "can_write": bool(frappe.has_permission("Attendance", "create") and frappe.has_permission("Attendance", "write")),
        "can_submit": bool(frappe.has_permission("Attendance", "submit")),
        "can_assign": bool(frappe.has_permission("Employee", "write"))}


@frappe.whitelist()
def available_workers(project):
    project = checked_project(project)
    return frappe.get_list("Employee", filters={"company": project.company, "status": "Active",
        "custom_construction_project": ["is", "not set"]}, fields=["name", "employee_name"],
        order_by="employee_name", limit_page_length=500)


@frappe.whitelist(methods=["POST"])
def assign_workers(project, employees):
    project = checked_project(project)
    names = frappe.parse_json(employees)
    if not isinstance(names, list) or not names or len(names) > 100:
        frappe.throw(_("Select up to 100 workers."))
    for name in sorted(set(names)):
        frappe.db.sql("select name from `tabEmployee` where name=%s for update", name)
        doc = frappe.get_doc("Employee", name)
        doc.check_permission("write")
        if doc.company != project.company or doc.status != "Active" or doc.custom_construction_project not in (None, "", project.name):
            frappe.throw(_("This worker is unavailable for this project. Refresh the crew list."))
        doc.custom_construction_project = project.name
        doc.save()
    return {"assigned": len(set(names))}


@frappe.whitelist(methods=["POST"])
def save_attendance(project, date, rows, confirm=False):
    project = checked_project(project)
    date = work_date(date)
    if project.status != "Open":
        frappe.throw(_("Attendance entry requires an open project."))
    rows = frappe.parse_json(rows)
    confirm = str(confirm).lower() in ("true", "1")
    if not isinstance(rows, list) or not rows or len(rows) > 100:
        frappe.throw(_("Mark at least one worker, up to 100 at a time."))
    if len({r.get("employee") for r in rows}) != len(rows):
        frappe.throw(_("A worker appears more than once."))
    result = []
    for row in sorted(rows, key=lambda r: r["employee"]):
        frappe.db.sql("select name from `tabEmployee` where name=%s for update", row["employee"])
        employee = frappe.get_doc("Employee", row["employee"])
        employee.check_permission("read")
        if employee.company != project.company or employee.custom_construction_project != project.name or employee.status != "Active":
            frappe.throw(_("This worker is not in this project's active crew."))
        status = row.get("status")
        regular, ot = hours(row.get("regular")), hours(row.get("ot"))
        if status not in ("Present", "Absent", "Half Day") or regular + ot > 24:
            frappe.throw(_("Choose present, absent or half day; total hours cannot exceed 24."))
        if (status == "Absent" and (regular or ot)) or (status != "Absent" and regular <= 0):
            frappe.throw(_("Absent workers must have zero hours; present workers need regular hours."))
        values = {"status": status, "custom_construction_regular_hours": regular,
            "actual_overtime_duration": ot, "working_hours": regular + ot,
            "standard_working_hours": regular, "overtime_type": row.get("overtime_type") or None}
        if values["overtime_type"]:
            frappe.get_doc("Overtime Type", values["overtime_type"]).check_permission("read")
        existing = frappe.get_all("Attendance", filters={"employee": employee.name, "attendance_date": date,
            "docstatus": ["<", 2]}, pluck="name")
        if len(existing) > 1:
            frappe.throw(_("Multiple attendance shifts exist; review this worker in advanced attendance."))
        if existing:
            doc = frappe.get_doc("Attendance", existing[0])
            doc.check_permission("read")
            if doc.custom_construction_project != project.name:
                frappe.throw(_("Attendance already exists outside this site sheet. Review it before making changes."))
            identical = all((doc.get(k) or None) == (v or None) for k, v in values.items())
            if doc.docstatus == 1:
                if not identical:
                    frappe.throw(_("Confirmed attendance cannot be overwritten. Use an attendance correction."))
                result.append(doc.name)
                continue
            if not identical and (row.get("name") != doc.name or str(doc.modified) != str(row.get("modified"))):
                frappe.throw(_("The crew sheet changed. Reload it before saving your changes."))
            doc.check_permission("write")
            doc.update(values)
            doc.save()
        else:
            if row.get("name"):
                frappe.throw(_("The attendance draft was removed. Reload the crew sheet."))
            doc = frappe.get_doc({"doctype": "Attendance", "employee": employee.name,
                "company": project.company, "attendance_date": date,
                "custom_construction_project": project.name, **values}).insert()
        # HRMS may replace status for approved leave; never silently accept different hours/status.
        if doc.status != status:
            frappe.throw(_("Approved leave conflicts with this mark. Review the worker's leave first."))
        if confirm:
            doc.submit()
        result.append(doc.name)
    return {"saved": len(result), "confirmed": confirm}


@frappe.whitelist()
def category_detail(project, category):
    project = checked_project(project)
    plan = plan_for(project.name)
    accounts = [r.account for r in plan.items if r.category == category] if plan else []
    if not accounts:
        frappe.throw(_("This category is not in the current project budget."))
    from hiru_construction.construction.report.construction_project_costs.construction_project_costs import execute
    rows = [r for r in execute({"project": project.name})[1] if r["account"] in accounts]
    entries = frappe.get_list("GL Entry", filters={"project": project.name, "company": project.company,
        "account": ["in", accounts], "is_cancelled": 0, "voucher_type": ["!=", "Period Closing Voucher"]},
        fields=["posting_date", "voucher_type", "voucher_no", "debit", "credit", "remarks"],
        order_by="posting_date desc, creation desc", limit_page_length=51)
    category = frappe.get_doc("Construction Cost Category", category)
    category.check_permission("read")
    invoices = [entry.voucher_no for entry in entries if entry.voucher_type == "Purchase Invoice"]
    suppliers = {doc.name: doc.supplier_name for doc in frappe.get_list("Purchase Invoice",
        filters={"name": ["in", invoices]}, fields=["name", "supplier_name"], limit_page_length=50)} \
        if invoices and frappe.has_permission("Purchase Invoice", "read") else {}
    for entry in entries:
        entry["description"] = suppliers.get(entry.voucher_no) or strip_html(entry.remarks or "")[:200]
        entry["note"] = strip_html(entry.remarks or "")[:200] if entry.voucher_no in suppliers else ""
    return {"label": category.category_name, "scope": category.scope, "description": category.description,
        "original": sum(r["original_budget"] for r in rows), "budget": sum(r["current_budget"] for r in rows),
        "spent": sum(r["actual"] for r in rows), "orders": sum(r["commitment"] for r in rows),
        "remaining": None if any(r["reconciliation"] for r in rows) else sum(r["remaining_budget"] for r in rows),
        "entries": entries[:50], "has_more": len(entries) > 50}
