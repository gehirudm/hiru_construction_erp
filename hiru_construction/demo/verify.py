"""Integration checks against posted ERPNext/HRMS records, not a parallel ledger."""

import json

import frappe
from frappe.utils import flt

COMPANY = "Hiru Construction Demo"
PROJECT = "PILOT-PROJECT-001"


def equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main():
    if not frappe.conf.get("hiru_pilot"):
        raise RuntimeError("Verification is restricted to the pilot site")
    installed = frappe.get_installed_apps()
    for app in ("erpnext", "hrms", "hiru_construction"):
        equal(app in installed, True, f"{app} installed")
    equal(frappe.db.get_value("Company", COMPANY, "default_currency"), "LKR", "currency")
    equal(frappe.db.count("Project", {"company": COMPANY}), 1, "project count")
    equal(frappe.db.count("Task", {"project": PROJECT}), 3, "task count")
    equal(frappe.db.count("Budget", {"project": PROJECT, "docstatus": 1}), 4, "budgets")
    po = frappe.get_doc("Purchase Order", "PILOT-PO-001")
    equal(po.docstatus, 1, "PO submitted")
    equal(flt(po.grand_total), 100000, "PO amount")
    equal(flt(po.per_billed), 40, "PO billed percent")
    open_commitment = sum(flt(row.base_amount) - flt(row.billed_amt) for row in po.items)
    equal(open_commitment, 60000, "outstanding purchase commitment")

    actuals = {}
    for category, expected in [("Subcontractors", 40000), ("Labour", 81000),
                               ("Fuel", 9000), ("Materials", 2000)]:
        actual = frappe.db.sql("""
            select coalesce(sum(debit-credit), 0) from `tabGL Entry`
            where company=%s and project=%s and account=%s and is_cancelled=0
        """, (COMPANY, PROJECT, f"PILOT {category} - HCD"))[0][0]
        equal(flt(actual), expected, category + " project GL cost")
        actuals[category] = flt(actual)
    balance = frappe.db.sql("""
        select coalesce(sum(debit-credit), 0) from `tabGL Entry`
        where company=%s and is_cancelled=0
    """, COMPANY)[0][0]
    equal(flt(balance, 2), 0, "company ledger balanced")
    for i, expected in [(1, 60000), (2, 18000), (3, 3000)]:
        slips = frappe.get_all("Salary Slip", filters={"payroll_entry": f"PILOT-PAYROLL-FIXED-{i:03}"},
                               fields=["name", "docstatus", "gross_pay", "net_pay"])
        equal(len(slips), 1, f"worker {i} salary slip count")
        equal(slips[0].docstatus, 1, f"worker {i} salary submitted")
        equal(flt(slips[0].net_pay), expected, f"worker {i} salary net pay")
    equal(frappe.db.count("Attendance", {"company": COMPANY, "docstatus": 1}), 3, "attendance")
    equal(flt(frappe.db.get_value("Timesheet", "PILOT-TIME-001", "total_hours")), 8, "site hours")
    equal(flt(frappe.db.get_value("Vehicle", "PILOT-TRUCK-01", "last_odometer")), 10300, "odometer")
    equal(frappe.db.count("Expense Claim", {"vehicle_log": "PILOT-FUEL-001", "docstatus": 1}),
          1, "fuel claim count")
    equal(flt(frappe.db.get_value("Bin", {"item_code": "PILOT-TILE-BOX",
               "warehouse": "PILOT Site Store - HCD"}, "actual_qty")), 6, "stock on hand")
    from hiru_construction.construction.report.construction_project_costs.construction_project_costs import execute
    rows = execute({"project": PROJECT})[1]
    equal(sum(row["current_budget"] for row in rows), 375000, "report budget")
    equal(sum(row["actual"] for row in rows), 132000, "report actuals")
    equal(sum(row["commitment"] for row in rows), 60000, "report commitments")
    equal(sum(row["remaining_budget"] for row in rows), 183000, "report budget remaining")
    print(json.dumps({"passed": True, "project_actuals_lkr": actuals,
                      "open_commitments_lkr": open_commitment,
                      "total_actual_lkr": sum(actuals.values())}, indent=2))


if __name__ in ("__main__", "<run_path>"):
    main()
