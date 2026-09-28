"""Minimal business setup exclusively for the isolated automated-test site."""
import frappe
from frappe.utils import nowdate


def prepare():
    if not frappe.conf.get("hiru_test"):
        raise RuntimeError("Test setup requires a marked test site")
    if not frappe.db.exists("Company", "Cost Controls Test"):
        from erpnext.setup.setup_wizard.setup_wizard import setup_complete
        year = nowdate()[:4]
        setup_complete(frappe._dict(company_name="Cost Controls Test", company_abbr="CCT",
            country="Sri Lanka", currency="LKR", chart_of_accounts="Standard",
            fy_start_date=f"{year}-01-01", fy_end_date=f"{year}-12-31",
            domain="Services", bank_account="Test Bank"))
    if not frappe.db.exists("Gender", "Male"):
        frappe.get_doc({"doctype": "Gender", "gender": "Male"}).insert()
    frappe.db.commit()
