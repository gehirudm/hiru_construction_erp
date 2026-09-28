"""Versioned extensions to standard HRMS and accounting documents."""
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields({
        "Employee": [{"fieldname": "custom_construction_project", "label": "Site Project",
            "fieldtype": "Link", "options": "Project", "insert_after": "company"}],
        "Attendance": [
            {"fieldname": "custom_construction_project", "label": "Site Project", "fieldtype": "Link", "options": "Project"},
            {"fieldname": "custom_construction_regular_hours", "label": "Regular Site Hours", "fieldtype": "Float"},
        ],
        "Purchase Invoice": [
            {"fieldname": "custom_construction_vehicle", "label": "Fuel Vehicle", "fieldtype": "Link", "options": "Vehicle"},
            {"fieldname": "custom_construction_machine", "label": "Fuel Machinery Asset", "fieldtype": "Link", "options": "Asset"},
            {"fieldname": "custom_construction_litres", "label": "Fuel Litres", "fieldtype": "Float", "precision": "3"},
            {"fieldname": "custom_construction_meter", "label": "Odometer / Engine Hours", "fieldtype": "Float", "precision": "3"},
            {"fieldname": "custom_construction_meter_recorded", "label": "Meter Reading Recorded", "fieldtype": "Check"},
        ],
    })
    # Upgrade the named default category; custom categories select their own flow.
    for name in frappe.get_all("Construction Cost Category", filters={"category_name": "Fuel"}, pluck="name"):
        frappe.db.set_value("Construction Cost Category", name, "entry_type", "Fuel")
