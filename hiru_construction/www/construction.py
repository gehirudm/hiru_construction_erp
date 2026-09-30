import frappe
from hiru_construction.daily import require_manager

no_cache = 1
sitemap = 0


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=%2Fconstruction"
        raise frappe.Redirect
    from hiru_construction.site_access import is_owner
    if "Construction Supervisor" in frappe.get_roles() and not is_owner():
        frappe.local.flags.redirect_location = "/site-work"
        raise frappe.Redirect
    require_manager()
    context.is_owner = is_owner()
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.display_name = frappe.get_cached_value("User", frappe.session.user, "full_name")
    context.asset_version = "daily-5"
