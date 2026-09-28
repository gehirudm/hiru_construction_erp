import frappe

DEFAULT_CATEGORIES = (
    "Materials", "Labour", "Subcontractors", "Machinery and equipment", "Fuel",
    "Meals", "Transport", "Site overhead", "Permits and fees", "Other",
)


def after_install():
    from hiru_construction.quick_expense_fields import execute
    execute()
    for label in DEFAULT_CATEGORIES:
        if not frappe.db.exists("Construction Cost Category", {"category_name": label, "scope": "Global"}):
            frappe.get_doc({"doctype": "Construction Cost Category", "category_name": label,
                            "scope": "Global", "entry_type": "Meals" if label == "Meals" else "General"}).insert(ignore_permissions=True)
    from hiru_construction.site_work_fields import execute as site_work_fields
    site_work_fields()
    from hiru_construction.meal_setup import execute as meal_setup
    meal_setup()


def execute():
    after_install()
