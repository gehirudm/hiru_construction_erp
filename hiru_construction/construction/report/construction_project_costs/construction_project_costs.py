"""Current project costs: submitted plan, expense GL, and open uninvoiced PO lines."""
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    project_name = (filters or {}).get("project")
    if not project_name:
        frappe.throw(_("Select a project."))
    if not set(frappe.get_roles()) & {"System Manager", "Projects Manager"}:
        frappe.throw(_("Only project cost managers can view this report."), frappe.PermissionError)
    project = frappe.get_doc("Project", project_name)
    project.check_permission("read")
    if not project.company:
        frappe.throw(_("Set the project's company first."))
    currency = frappe.get_cached_value("Company", project.company, "default_currency")
    baseline_names = frappe.get_all("Construction Cost Plan", filters={"project": project_name,
        "docstatus": 1, "version_kind": "Tender baseline"}, pluck="name")
    if len(baseline_names) != 1:
        frappe.throw(_("Submit exactly one tender baseline for this project before viewing costs."))
    baseline = frappe.get_doc("Construction Cost Plan", baseline_names[0])
    baseline.check_permission("read")
    revisions = frappe.get_all("Construction Cost Plan", filters={"baseline": baseline.name,
        "docstatus": 1, "version_kind": "Approved revision", "status": "Approved"},
        order_by="revision_number desc", pluck="name")
    if len(revisions) > 1:
        frappe.throw(_("Multiple current revisions exist. Review the cost plans before reporting."))
    current = frappe.get_doc("Construction Cost Plan", revisions[0]) if revisions else baseline
    current.check_permission("read")
    actuals, commitments, receipt_overlap = read_ledger_and_orders(project.name, project.company)
    rows = assemble_rows(baseline.items, current.items, bool(revisions), actuals, commitments, currency, receipt_overlap)
    totals = {key: sum(row[key] or 0 for row in rows) for key in
              ("current_budget", "actual", "commitment", "exposure", "remaining_budget")}
    if receipt_overlap:
        totals["remaining_budget"] = None
    groups = defaultdict(lambda: {"current_budget": 0, "actual": 0, "commitment": 0})
    for row in rows:
        for key in groups[row["category"]]:
            groups[row["category"]][key] += row[key]
    chart = {"type": "bar", "data": {"labels": list(groups), "datasets": [
        {"name": label, "values": [g[key] for g in groups.values()]}
        for key, label in (("current_budget", _("Budget")), ("actual", _("Actual")),
                           ("commitment", _("Open orders")))]}}
    summary = [{"label": label, "value": _("Review receipts") if totals[key] is None else totals[key],
                "datatype": "Data" if totals[key] is None else "Currency", "currency": currency,
                "indicator": "Orange" if totals[key] is None else (
                    "Red" if key == "remaining_budget" and totals[key] < 0 else "Blue")}
               for key, label in (("current_budget", _("Current budget")), ("actual", _("Actual")),
                   ("commitment", _("Open orders")), ("remaining_budget", _("Budget remaining")))]
    message = _("Current submitted budget; all posted project expense entries and current uninvoiced order balances. "
                "Open orders are net of discounts and exclude taxes. Contingency is shown separately. "
                "Actual plus open orders is known exposure, not a forecast of final cost. Unmapped accounts remain visible.")
    if receipt_overlap:
        message += " " + _("Received but uninvoiced orders need reconciliation: their costs may already be in the ledger. "
            "Combined exposure and remaining budget are omitted for affected accounts and for the project total.")
    return columns(), rows, message, chart, summary


def read_ledger_and_orders(project, company):
    actuals = {row.account: flt(row.amount) for row in frappe.db.sql("""
        select gl.account, sum(gl.debit-gl.credit) amount
        from `tabGL Entry` gl join `tabAccount` a on a.name=gl.account
        where gl.project=%s and gl.company=%s and gl.is_cancelled=0 and a.root_type='Expense'
        and gl.voucher_type != 'Period Closing Voucher'
        group by gl.account
    """, (project, company), as_dict=True)}
    orders = frappe.db.sql("""
        select i.expense_account account, i.amount, i.base_net_amount, i.billed_amt, i.qty, i.received_qty
        from `tabPurchase Order Item` i join `tabPurchase Order` p on p.name=i.parent
        where p.company=%s and i.project=%s and p.docstatus=1
        and p.status not in ('Closed', 'Cancelled')
    """, (company, project), as_dict=True)
    commitments = defaultdict(float)
    receipt_overlap = set()
    for row in orders:
        # billed_amt and amount share the order currency; the ratio also handles discounts.
        # base_net_amount is already in company currency, avoiding mixed-currency subtraction.
        if flt(row.amount) > 0:
            billed_fraction = flt(row.billed_amt) / flt(row.amount)
            outstanding = flt(row.base_net_amount) * max(0, 1 - billed_fraction)
            commitments[row.account or ""] += outstanding
            if outstanding > 0 and flt(row.qty) > 0 and flt(row.received_qty) / flt(row.qty) > billed_fraction + 0.000001:
                receipt_overlap.add(row.account or "")
    return actuals, commitments, receipt_overlap


def assemble_rows(baseline, current, is_revision, actuals, commitments, currency, receipt_overlap=()):
    original = {row.account: row for row in baseline}
    mapping = {row.account: row for row in current}
    rows = []
    for account in sorted(set(original) | set(mapping) | set(actuals) | set(commitments)):
        line = mapping.get(account)
        source = original.get(account)
        actual, commitment = flt(actuals.get(account), 2), flt(commitments.get(account), 2)
        budget = flt(line.approved_revision if is_revision else line.original_estimate, 2) if line else 0
        category = frappe.get_cached_value("Construction Cost Category", line.category, "category_name") if line else _("Unmapped")
        rows.append({"account": account, "category": category, "currency": currency,
            "original_budget": flt(source.original_estimate, 2) if source else 0,
            "current_budget": budget, "contingency": flt(line.contingency, 2) if line else 0,
            "actual": actual, "commitment": commitment,
            "exposure": None if account in receipt_overlap else actual + commitment,
            "remaining_budget": None if account in receipt_overlap else flt(budget - actual - commitment, 2),
            "mapping_status": _("Mapped") if line else _("Needs mapping"),
            "reconciliation": _("Review unbilled receipts") if account in receipt_overlap else ""})
    return rows


def columns():
    return [
        {"fieldname": "category", "label": _("Category"), "fieldtype": "Data", "width": 160},
        {"fieldname": "account", "label": _("Expense Account"), "fieldtype": "Link", "options": "Account", "width": 200},
        {"fieldname": "currency", "label": _("Currency"), "fieldtype": "Link", "options": "Currency", "hidden": 1},
        *[{"fieldname": key, "label": label, "fieldtype": "Currency", "options": "currency", "width": 140}
          for key, label in (("original_budget", _("Original tender")), ("current_budget", _("Current budget")),
              ("contingency", _("Contingency reserve")), ("actual", _("Actual")), ("commitment", _("Open orders")),
              ("exposure", _("Known exposure")), ("remaining_budget", _("Budget remaining")))],
        {"fieldname": "mapping_status", "label": _("Mapping"), "fieldtype": "Data", "width": 130},
        {"fieldname": "reconciliation", "label": _("Reconciliation"), "fieldtype": "Data", "width": 180},
    ]
