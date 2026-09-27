from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields({"Purchase Invoice": [
        {"fieldname": "custom_construction_entry_id", "label": "Construction Entry ID",
         "fieldtype": "Data", "unique": 1, "hidden": 1, "read_only": 1, "no_copy": 1},
        {"fieldname": "custom_construction_request_hash", "label": "Construction Request Hash",
         "fieldtype": "Data", "hidden": 1, "read_only": 1, "no_copy": 1},
        {"fieldname": "custom_construction_category", "label": "Construction Category",
         "fieldtype": "Link", "options": "Construction Cost Category", "read_only": 1},
    ]})
