import frappe

DEFAULT_CATEGORIES = (
    "Materials", "Labour", "Subcontractors", "Machinery and equipment", "Fuel",
    "Transport", "Site overhead", "Permits and fees", "Other",
)


def after_install():
    from hiru_construction.quick_expense_fields import execute
    execute()
    for label in DEFAULT_CATEGORIES:
        if not frappe.db.exists("Construction Cost Category", {"category_name": label, "scope": "Global"}):
            frappe.get_doc({"doctype": "Construction Cost Category", "category_name": label,
                            "scope": "Global"}).insert(ignore_permissions=True)


def execute():
    after_install()
