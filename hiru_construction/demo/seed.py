"""Optional synthetic fixtures. Run explicitly with make seed; never on install."""

import json

import frappe
from frappe.utils import getdate

COMPANY = "Hiru Construction Demo"
ABBR = "HCD"
PROJECT = "PILOT-PROJECT-001"
DATE = "2026-09-21"
CATEGORIES = [
    "Materials", "Labour", "Subcontractors", "Machinery and equipment", "Fuel",
    "Meals", "Transport", "Site overhead", "Permits and fees", "Other",
]


def ensure(doctype, name, values, submit=False):
    """Use stable IDs; reruns never recreate a submitted transaction."""
    if frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        if doc.docstatus == 2:
            raise ValueError(f"{doctype} {name} was cancelled; review before reseeding")
    else:
        doc = frappe.get_doc({"doctype": doctype, **values}).insert(set_name=name)
    if submit and doc.docstatus == 0:
        doc.submit()
    return doc


def account(category):
    return f"PILOT {category} - {ABBR}"


def setup_company():
    from erpnext.setup.setup_wizard.setup_wizard import setup_complete
    from frappe.desk.page.setup_wizard.setup_wizard import enable_setup_wizard_complete

    if not frappe.db.exists("Company", COMPANY):
        setup_complete(frappe._dict(
            company_name=COMPANY, company_abbr=ABBR, country="Sri Lanka", currency="LKR",
            chart_of_accounts="Standard", fy_start_date="2026-01-01",
            fy_end_date="2026-12-31", domain="Services", bank_account="PILOT Bank",
        ))
    frappe.db.set_single_value("System Settings", {
        "setup_complete": 1, "language": "en", "time_zone": "Asia/Colombo",
    })
    for app in ("frappe", "erpnext"):
        enable_setup_wizard_complete(app)
    frappe.db.set_single_value("Payroll Settings", {
        "email_salary_slip_to_employee": 0, "payroll_based_on": "Attendance",
    })
    company = frappe.get_doc("Company", COMPANY)
    payroll_payable = frappe.get_doc("Account", company.default_payroll_payable_account)
    if payroll_payable.account_type != "Payable":
        payroll_payable.account_type = "Payable"
        payroll_payable.save()
    parent = frappe.db.get_value("Account", company.default_expense_account, "parent_account")
    for category in CATEGORIES:
        ensure("Account", account(category), {
            "account_name": f"PILOT {category}", "company": COMPANY,
            "parent_account": parent, "root_type": "Expense", "is_group": 0,
        })
    ensure("Holiday List", "PILOT Seven Day Calendar", {
        "holiday_list_name": "PILOT Seven Day Calendar",
        "from_date": "2026-01-01", "to_date": "2026-12-31", "holidays": [],
    })
    company.default_holiday_list = "PILOT Seven Day Calendar"
    company.save()
    ensure("Holiday List Assignment", "PILOT-HOLIDAY-ASSIGNMENT", {
        "applicable_for": "Company", "assigned_to": COMPANY,
        "holiday_list": "PILOT Seven Day Calendar", "from_date": "2026-01-01",
    }, submit=True)
    frappe.db.commit()
    return company


def setup_project(company):
    ensure("Project", PROJECT, {
        "project_name": "DEMO — Community Hall Renovation", "company": COMPANY,
        "expected_start_date": DATE, "expected_end_date": "2026-10-30",
        "cost_center": company.cost_center,
        "notes": "Synthetic pilot only. All people, prices, quantities and dates are examples.",
    })
    previous = None
    for i, (subject, start, end) in enumerate([
        ("Site preparation", DATE, "2026-09-23"),
        ("Floor preparation", "2026-09-24", "2026-09-27"),
        ("Lay floor tiles", "2026-09-28", "2026-10-07"),
    ], 1):
        task = ensure("Task", f"PILOT-TASK-{i:03}", {
            "subject": f"DEMO — {subject}", "project": PROJECT,
            "exp_start_date": start, "exp_end_date": end,
            "depends_on": [{"task": previous}] if previous else [],
        })
        previous = task.name
    for category, amount in [("Subcontractors", 150000), ("Labour", 150000),
                             ("Fuel", 25000), ("Materials", 50000)]:
        ensure("Budget", f"PILOT-BUDGET-{frappe.scrub(category).upper()}", {
            "company": COMPANY, "budget_against": "Project", "project": PROJECT,
            "account": account(category), "budget_amount": amount,
            "from_fiscal_year": "2026", "to_fiscal_year": "2026",
            "distribution_frequency": "Yearly", "distribute_equally": 1,
            "applicable_on_purchase_order": 1, "applicable_on_booking_actual_expenses": 1,
            "action_if_annual_budget_exceeded": "Warn",
            "action_if_annual_budget_exceeded_on_po": "Warn",
        }, submit=True)


def setup_purchase(company):
    from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

    supplier = ensure("Supplier", "PILOT Supplier", {
        "supplier_name": "PILOT Supplier", "supplier_group": "All Supplier Groups",
        "supplier_type": "Company",
    })
    ensure("Item", "PILOT-TILING-SERVICE", {
        "item_code": "PILOT-TILING-SERVICE", "item_name": "DEMO tiling service",
        "item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 0,
        "item_defaults": [{"company": COMPANY, "expense_account": account("Subcontractors"),
                           "buying_cost_center": company.cost_center}],
    })
    po = ensure("Purchase Order", "PILOT-PO-001", {
        "company": COMPANY, "supplier": supplier.name, "transaction_date": DATE,
        "schedule_date": "2026-10-07", "currency": "LKR", "conversion_rate": 1,
        "items": [{"item_code": "PILOT-TILING-SERVICE", "qty": 10, "rate": 10000,
                   "schedule_date": "2026-10-07", "project": PROJECT,
                   "expense_account": account("Subcontractors"),
                   "cost_center": company.cost_center}],
    }, submit=True)
    if not frappe.db.exists("Purchase Invoice", "PILOT-PINV-001"):
        invoice = make_purchase_invoice(po.name)
        invoice.set_posting_time = 1
        invoice.posting_date = DATE
        invoice.due_date = "2026-10-21"
        invoice.bill_no = "DEMO-SUPPLIER-001"
        invoice.bill_date = DATE
        invoice.items[0].qty = 4
        invoice.insert(set_name="PILOT-PINV-001")
    ensure("Purchase Invoice", "PILOT-PINV-001", {}, submit=True)


def setup_cost_plan(company):
    lines = []
    for category, amount in [("Subcontractors", 150000), ("Labour", 150000),
                             ("Fuel", 25000), ("Materials", 50000)]:
        category_name = frappe.db.get_value("Construction Cost Category",
            {"category_name": category, "scope": "Global"}, "name")
        lines.append({"category": category_name, "account": account(category),
                      "original_estimate": amount, "contingency": 0})
    ensure("Construction Cost Plan", "PILOT-TENDER-001", {
        "plan_name": "PILOT-TENDER-001", "project": PROJECT,
        "version_kind": "Tender baseline", "items": lines,
    }, submit=True)


def setup_people(company):
    ensure("Gender", "Male", {"gender": "Male"})
    ensure("Salary Component", "PILOT Basic", {
        "salary_component": "PILOT Basic", "salary_component_abbr": "PBAS",
        "type": "Earning", "amount_based_on_formula": 1, "formula": "base",
        "depends_on_payment_days": 0,
        "accounts": [{"company": COMPANY, "account": account("Labour")}],
    })
    for i, frequency, base, start, end in [
        (1, "Monthly", 60000, "2026-09-01", "2026-09-30"),
        (2, "Weekly", 18000, "2026-09-21", "2026-09-27"),
        (3, "Daily", 3000, DATE, DATE),
    ]:
        employee = ensure("Employee", f"PILOT-EMP-{i:03}", {
            "first_name": f"Demo Worker {i}", "gender": "Male",
            "date_of_birth": "1990-01-01", "date_of_joining": "2026-09-01",
            "company": COMPANY, "status": "Active",
            "holiday_list": "PILOT Seven Day Calendar",
            "payroll_cost_center": company.cost_center,
            "custom_construction_project": PROJECT,
        })
        if not employee.custom_construction_project:
            employee.custom_construction_project = PROJECT
            employee.save()
        ensure("Attendance", f"PILOT-ATT-{i:03}", {
            "employee": employee.name, "company": COMPANY,
            "attendance_date": DATE, "status": "Present",
        }, submit=True)
        structure = ensure("Salary Structure", f"PILOT {frequency} Fixed", {
            "company": COMPANY, "currency": "LKR", "payroll_frequency": frequency,
            "is_active": "Yes", "earnings": [{"salary_component": "PILOT Basic",
                "amount_based_on_formula": 1, "formula": "base", "depends_on_payment_days": 0}],
        }, submit=True)
        ensure("Salary Structure Assignment", f"PILOT-SSA-FIXED-{i:03}", {
            "employee": employee.name, "salary_structure": structure.name,
            "from_date": "2026-09-01", "company": COMPANY, "currency": "LKR", "base": base,
        }, submit=True)
        payable = company.default_payroll_payable_account or company.default_payable_account
        payroll = ensure("Payroll Entry", f"PILOT-PAYROLL-FIXED-{i:03}", {
            "company": COMPANY, "posting_date": end, "start_date": start, "end_date": end,
            "payroll_frequency": frequency, "currency": "LKR", "exchange_rate": 1,
            "payroll_payable_account": payable, "cost_center": company.cost_center,
            "project": PROJECT, "validate_attendance": 0,
            "employees": [{"employee": employee.name}],
        }, submit=True)
        if not payroll.salary_slips_submitted:
            payroll.submit_salary_slips()

    ensure("Activity Type", "PILOT Site Work", {"activity_type": "PILOT Site Work"})
    ensure("Timesheet", "PILOT-TIME-001", {
        "company": COMPANY, "employee": "PILOT-EMP-001",
        "time_logs": [{"activity_type": "PILOT Site Work", "project": PROJECT,
                       "task": "PILOT-TASK-001", "from_time": DATE + " 08:00:00",
                       "to_time": DATE + " 16:00:00", "hours": 8,
                       "is_billable": 0, "costing_rate": 0}],
    }, submit=True)


def setup_materials(company):
    warehouse = ensure("Warehouse", "PILOT Site Store - HCD", {
        "warehouse_name": "PILOT Site Store", "company": COMPANY,
        "parent_warehouse": "All Warehouses - HCD",
    })
    ensure("Item", "PILOT-TILE-BOX", {
        "item_code": "PILOT-TILE-BOX", "item_name": "DEMO tile box",
        "item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 1,
        "item_defaults": [{"company": COMPANY, "default_warehouse": warehouse.name,
                           "expense_account": account("Materials")}],
    })
    ensure("Stock Entry", "PILOT-STOCK-RECEIPT", {
        "company": COMPANY, "stock_entry_type": "Material Receipt",
        "posting_date": DATE, "posting_time": "09:00:00", "set_posting_time": 1,
        "items": [{"item_code": "PILOT-TILE-BOX", "qty": 10,
                   "t_warehouse": warehouse.name, "basic_rate": 500,
                   "expense_account": company.stock_adjustment_account,
                   "cost_center": company.cost_center}],
    }, submit=True)
    ensure("Stock Entry", "PILOT-STOCK-ISSUE", {
        "company": COMPANY, "stock_entry_type": "Material Issue", "project": PROJECT,
        "posting_date": DATE, "posting_time": "10:00:00", "set_posting_time": 1,
        "items": [{"item_code": "PILOT-TILE-BOX", "qty": 4,
                   "s_warehouse": warehouse.name, "expense_account": account("Materials"),
                   "cost_center": company.cost_center}],
    }, submit=True)


def setup_fuel(company):
    from hrms.hr.doctype.vehicle_log.vehicle_log import make_expense_claim

    vehicle = ensure("Vehicle", "PILOT-TRUCK-01", {
        "license_plate": "PILOT-TRUCK-01", "make": "Demo", "model": "Truck",
        "last_odometer": 10000, "fuel_type": "Diesel", "uom": "Litre", "company": COMPANY,
    })
    if not vehicle.company:
        vehicle.company = COMPANY
        vehicle.save()
    log = ensure("Vehicle Log", "PILOT-FUEL-001", {
        "license_plate": "PILOT-TRUCK-01", "employee": "PILOT-EMP-001",
        "date": DATE, "last_odometer": 10000, "odometer": 10300,
        "fuel_qty": 30, "price": 300,
    }, submit=True)
    ensure("Expense Claim Type", "PILOT Fuel", {
        "expense_type": "PILOT Fuel",
        "accounts": [{"company": COMPANY, "default_account": account("Fuel")}],
    })
    if not frappe.db.exists("Expense Claim", "PILOT-FUEL-CLAIM-001"):
        claim = frappe.get_doc(make_expense_claim(log.name))
        claim.company = COMPANY
        claim.posting_date = DATE
        claim.project = PROJECT
        claim.cost_center = company.cost_center
        claim.payable_account = company.default_expense_claim_payable_account or company.default_payable_account
        claim.expense_approver = "Administrator"
        claim.approval_status = "Approved"
        claim.expenses[0].expense_type = "PILOT Fuel"
        claim.expenses[0].cost_center = company.cost_center
        claim.expenses[0].project = PROJECT
        claim.expenses[0].sanctioned_amount = 9000
        claim.insert(set_name="PILOT-FUEL-CLAIM-001")
    ensure("Expense Claim", "PILOT-FUEL-CLAIM-001", {}, submit=True)


def setup_meals(company):
    from hiru_construction.daily import plan_for
    project = frappe.get_doc("Project", PROJECT)
    if not project.custom_construction_meal_rates:
        for meal_type, rate in (("Breakfast", 200), ("Lunch", 350), ("Dinner", 300)):
            project.append("custom_construction_meal_rates", {"meal_type": meal_type, "expected_per_head": rate})
        project.save()
    current = plan_for(PROJECT)
    if any(row.account == account("Meals") for row in current.items):
        return
    if frappe.db.exists("Construction Cost Plan", "PILOT-MEALS-BUDGET-001"):
        raise ValueError("The sample Meals revision is no longer active; review the project budget before reseeding")
    items = [{"category": row.category, "account": row.account, "original_estimate": row.original_estimate,
        "approved_revision": row.approved_revision if current.version_kind == "Approved revision" else row.original_estimate,
        "contingency": row.contingency} for row in current.items]
    items.append({"category": frappe.db.get_value("Construction Cost Category", {"category_name": "Meals", "scope": "Global"}, "name"),
        "account": account("Meals"), "original_estimate": 0, "approved_revision": 30000})
    ensure("Construction Cost Plan", "PILOT-MEALS-BUDGET-001", {"plan_name": "PILOT-MEALS-BUDGET-001",
        "project": PROJECT, "version_kind": "Approved revision", "baseline": "PILOT-TENDER-001", "items": items}, submit=True)


def setup_workspace():
    if frappe.get_meta("User").has_field("default_workspace"):
        frappe.db.set_value("User", "Administrator", "default_workspace", None)


def main():
    if not frappe.conf.get("hiru_pilot"):
        raise RuntimeError("Seed is restricted to sites explicitly marked hiru_pilot")
    if getdate() < getdate(DATE):
        raise RuntimeError("Pilot attendance date must not be in the future")
    if frappe.get_all("Company", filters={"name": ["!=", COMPANY]}, limit=1):
        raise RuntimeError("Refusing to seed alongside other companies")
    company = setup_company()
    for fn in [setup_project, setup_purchase, setup_people, setup_materials, setup_fuel, setup_cost_plan, setup_meals]:
        fn(company)
        frappe.db.commit()
        print(f"Completed {fn.__name__}")
    setup_workspace()
    frappe.db.commit()
    frappe.clear_cache()
    print(json.dumps({"company": COMPANY, "project": PROJECT, "synthetic": True}))


if __name__ in ("__main__", "<run_path>"):
    main()
