"""Accessible posted project costs, grouped by document and budget category."""
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import getdate, strip_html

from hiru_construction.daily import checked_project, plan_for


def amount_filter(value):
    if value in (None, ""):
        return None
    try:
        value = Decimal(str(value))
        if not value.is_finite() or abs(value) > Decimal("999999999999.99"):
            raise ValueError
        return value
    except (InvalidOperation, ValueError):
        frappe.throw(_("Enter a valid minimum or maximum amount."))


def assemble(entries, mapping, invoices, filters):
    grouped = OrderedDict()
    for entry in entries:
        category, label = mapping.get(entry.account, ("__unmapped__", "Unmapped"))
        key = (str(entry.posting_date), entry.voucher_type, entry.voucher_no, category)
        item = grouped.setdefault(key, {"date": str(entry.posting_date), "source": entry.voucher_type,
            "reference": entry.voucher_no, "category": category, "category_label": label,
            "party": "", "description": "", "amount": Decimal(0), "accounts": set(),
            "order": str(entry.creation) + entry.name})
        item["amount"] += Decimal(str(entry.debit or 0)) - Decimal(str(entry.credit or 0))
        item["accounts"].add(entry.account)
        invoice = invoices.get(entry.voucher_no) if entry.voucher_type == "Purchase Invoice" else None
        item["party"] = (invoice.supplier_name if invoice else entry.party) or item["party"]
        text = strip_html((invoice.remarks if invoice else entry.remarks) or "")
        if text and not item["description"]:
            item["description"] = text[:500]
    rows = sorted(grouped.values(), key=lambda row: (row["date"], row["order"], row["source"], row["reference"], row["category"]))
    sources = sorted({row["source"] for row in rows})
    categories = sorted({(row["category"], row["category_label"]) for row in rows}, key=lambda pair: (pair[1], pair[0]))
    minimum, maximum = amount_filter(filters.get("minimum")), amount_filter(filters.get("maximum"))
    if minimum is not None and maximum is not None and minimum > maximum:
        frappe.throw(_("Minimum amount must not exceed maximum amount."))
    search = str(filters.get("search") or "").strip().casefold()
    result, total = [], Decimal(0)
    for row in rows:
        if filters.get("category") and row["category"] != filters["category"]:
            continue
        if filters.get("source") and row["source"] != filters["source"]:
            continue
        if filters.get("from_date") and row["date"] < filters["from_date"]:
            continue
        if filters.get("to_date") and row["date"] > filters["to_date"]:
            continue
        if minimum is not None and row["amount"] < minimum or maximum is not None and row["amount"] > maximum:
            continue
        if search and search not in " ".join([row["reference"], row["party"], row["description"], *sorted(row["accounts"])]).casefold():
            continue
        total += row["amount"]
        result.append({**{k: v for k, v in row.items() if k not in ("accounts", "order", "amount")},
            "amount": float(row["amount"]), "running_total": float(total)})
    return result, float(total), sources, categories


@frappe.whitelist()
def listing(project, filters=None, page=1, page_size=50):
    project = checked_project(project)
    frappe.has_permission("GL Entry", "read", throw=True)
    filters = frappe.parse_json(filters) if filters else {}
    if not isinstance(filters, dict):
        frappe.throw(_("Expense filters must be an object."))
    for field in ("from_date", "to_date"):
        if filters.get(field):
            filters[field] = str(getdate(filters[field]))
    if filters.get("from_date") and filters.get("to_date") and filters["from_date"] > filters["to_date"]:
        frappe.throw(_("Start date must not be after end date."))
    try:
        page, page_size = int(page), int(page_size)
        if page < 1 or page_size not in (25, 50, 100):
            raise ValueError
    except (ValueError, TypeError):
        frappe.throw(_("Choose a valid page and a page size of 25, 50 or 100."))
    plan = plan_for(project.name)
    mapping = {row.account: (row.category, frappe.get_cached_value("Construction Cost Category", row.category, "category_name"))
        for row in plan.items} if plan else {}
    accounts = frappe.get_all("Account", filters={"company": project.company, "root_type": "Expense", "is_group": 0}, pluck="name")
    entries = frappe.get_list("GL Entry", filters={"project": project.name, "company": project.company,
        "account": ["in", accounts], "is_cancelled": 0, "voucher_type": ["!=", "Period Closing Voucher"]},
        fields=["name", "posting_date", "creation", "voucher_type", "voucher_no", "account", "party", "remarks", "debit", "credit"],
        order_by="posting_date asc, creation asc, name asc", limit_page_length=0) if accounts else []
    names = list({row.voucher_no for row in entries if row.voucher_type == "Purchase Invoice"})
    invoices = {}
    if names and frappe.has_permission("Purchase Invoice", "read"):
        for start in range(0, len(names), 500):
            invoices.update({row.name: row for row in frappe.get_list("Purchase Invoice", filters={"name": ["in", names[start:start + 500]]},
                fields=["name", "supplier_name", "remarks"], limit_page_length=0)})
    rows, total, sources, categories = assemble(entries, mapping, invoices, filters)
    page = min(page, max(1, (len(rows) + page_size - 1) // page_size))
    start = (page - 1) * page_size
    return {"rows": rows[start:start + page_size], "total": total, "count": len(rows),
        "opening_total": rows[start - 1]["running_total"] if start and start <= len(rows) else 0,
        "page": page, "page_size": page_size, "has_more": start + page_size < len(rows),
        "currency": frappe.get_cached_value("Company", project.company, "default_currency"),
        "sources": sources, "categories": [{"value": key, "label": label} for key, label in categories]}
