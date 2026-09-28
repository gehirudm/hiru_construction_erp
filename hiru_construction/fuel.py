"""Fuel details live on the accounting invoice, linked to standard fleet/assets."""
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import flt, getdate

from hiru_construction.daily import checked_project


def number(value, positive=False):
    try:
        value = Decimal(str(value))
        if not value.is_finite() or value < 0 or value > Decimal("999999999") or (positive and value == 0):
            raise ValueError
        if value != value.quantize(Decimal(".001")):
            raise ValueError
        return float(value)
    except (InvalidOperation, ValueError, TypeError):
        frappe.throw(_("Enter valid fuel litres and a non-negative meter reading, with up to three decimal places."))


@frappe.whitelist()
def equipment(project):
    project = checked_project(project)
    vehicles = frappe.get_list("Vehicle", filters={"company": project.company},
        fields=["name", "make", "model", "last_odometer"], limit_page_length=500)
    machines = frappe.get_list("Asset", filters={"company": project.company, "docstatus": ["<", 2],
        "status": ["not in", ["Sold", "Scrapped"]]}, fields=["name", "asset_name"], limit_page_length=500)
    return {"vehicles": vehicles, "machines": machines}


def validate_invoice(doc, method=None):
    if not doc.custom_construction_entry_id:
        return
    is_fuel = frappe.db.get_value("Construction Cost Category", doc.custom_construction_category, "entry_type") == "Fuel"
    vehicle, machine = doc.custom_construction_vehicle, doc.custom_construction_machine
    if not is_fuel:
        if vehicle or machine or doc.custom_construction_litres:
            frappe.throw(_("Choose a fuel category for an equipment fuel expense."))
        return
    if bool(vehicle) == bool(machine):
        frappe.throw(_("Choose one vehicle or machinery asset for this fuel expense."))
    if vehicle and not doc.custom_construction_meter_recorded:
        frappe.throw(_("Enter the vehicle odometer reading."))
    number(doc.custom_construction_litres, positive=True)
    meter = number(doc.custom_construction_meter)
    doctype, name, field = ("Vehicle", vehicle, "custom_construction_vehicle") if vehicle else ("Asset", machine, "custom_construction_machine")
    # Serialize fuel posting for this equipment. Revalidation on submission catches stale drafts.
    frappe.db.sql(f"select name from `tab{doctype}` where name=%s for update", name)
    equipment = frappe.get_doc(doctype, name)
    equipment.check_permission("read")
    if equipment.company != doc.company or equipment.docstatus == 2:
        frappe.throw(_("Choose equipment belonging to this project's company."))
    if machine and equipment.status in ("Sold", "Scrapped"):
        frappe.throw(_("This machinery asset is no longer available."))
    previous = frappe.get_all("Purchase Invoice", filters={field: name, "docstatus": 1, "name": ["!=", doc.name or ""]},
        fields=["posting_date", "custom_construction_meter"], order_by="posting_date desc, custom_construction_meter desc", limit_page_length=1)
    floor = flt(equipment.last_odometer) if vehicle else 0
    last_date = None
    if previous:
        last_date = previous[0].posting_date
    readings = frappe.get_all("Purchase Invoice", filters={field: name, "docstatus": 1,
        "custom_construction_meter_recorded": 1, "name": ["!=", doc.name or ""]},
        pluck="custom_construction_meter", order_by="custom_construction_meter desc", limit_page_length=1)
    if readings:
        floor = max(floor, readings[0])
    if vehicle:
        logs = frappe.get_all("Vehicle Log", filters={"license_plate": vehicle, "docstatus": 1},
            pluck="date", order_by="date desc", limit_page_length=1)
        log_date = logs[0] if logs else None
        if log_date:
            last_date = max(getdate(last_date or log_date), getdate(log_date))
    if last_date and getdate(doc.posting_date) < getdate(last_date):
        frappe.throw(_("A later fuel or vehicle log exists. Enter readings in date order or review the history first."))
    if doc.custom_construction_meter_recorded and meter < floor:
        frappe.throw(_("The meter reading cannot be lower than the last recorded reading ({0}).").format(floor))


@frappe.whitelist()
def history(project):
    project = checked_project(project)
    return frappe.get_list("Purchase Invoice", filters={"project": project.name, "docstatus": 1,
        "custom_construction_litres": [">", 0]}, fields=["name", "posting_date", "grand_total",
        "custom_construction_vehicle", "custom_construction_machine", "custom_construction_litres",
        "custom_construction_meter", "custom_construction_meter_recorded"], order_by="posting_date desc, creation desc", limit_page_length=20)
