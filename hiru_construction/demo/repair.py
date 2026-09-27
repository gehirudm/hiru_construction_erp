"""One-time cancellation of zero-value records from the unfinished pilot."""
import frappe


def cancel_empty_payroll():
    if not frappe.conf.get("hiru_pilot"):
        raise RuntimeError("Development site only")
    for i in range(1, 4):
        name = f"PILOT-PAYROLL-{i:03}"
        if not frappe.db.exists("Payroll Entry", name):
            continue
        payroll = frappe.get_doc("Payroll Entry", name)
        if payroll.company != "Hiru Construction Demo":
            raise RuntimeError("Unexpected company")
        if payroll.docstatus == 1:
            slips = frappe.get_all("Salary Slip", filters={"payroll_entry": name},
                                  fields=["gross_pay", "net_pay", "journal_entry"])
            if any(s.gross_pay or s.net_pay or s.journal_entry for s in slips):
                raise RuntimeError("Refusing to cancel nonzero payroll")
            payroll.cancel()
        assignment_name = f"PILOT-SSA-{i:03}"
        if frappe.db.exists("Salary Structure Assignment", assignment_name):
            assignment = frappe.get_doc("Salary Structure Assignment", assignment_name)
            if assignment.docstatus == 1:
                assignment.cancel()
    frappe.db.commit()
