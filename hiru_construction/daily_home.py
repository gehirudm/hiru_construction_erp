import frappe


def execute():
    # Replace only the demo landing preference previously installed by our seed.
    if frappe.conf.get("hiru_pilot") and frappe.db.get_value("User", "Administrator", "default_workspace") == "Hiru Construction":
        frappe.db.set_value("User", "Administrator", "default_workspace", None)
        frappe.clear_cache(user="Administrator")
