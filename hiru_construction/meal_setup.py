import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    if not frappe.db.exists("Notification Type", "Construction Meal Alert"):
        frappe.get_doc({"doctype": "Notification Type", "type_name": "Construction Meal Alert", "enabled": 1}).insert(ignore_permissions=True)
    create_custom_fields({
        "Project": [{"fieldname": "custom_construction_meal_rates", "label": "Expected Meal Cost Per Person",
            "fieldtype": "Table", "options": "Construction Meal Rate"}],
        "Purchase Invoice": [{"fieldname": "custom_construction_meal", "label": "Site Meal",
            "fieldtype": "Link", "options": "Construction Meal"}],
    })
    if not frappe.db.exists("Construction Cost Category", {"category_name": "Meals", "scope": "Global"}):
        frappe.get_doc({"doctype": "Construction Cost Category", "category_name": "Meals",
            "scope": "Global", "entry_type": "Meals"}).insert(ignore_permissions=True)
