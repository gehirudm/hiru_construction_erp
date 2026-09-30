import frappe
from hiru_construction.site_access import require_site_user, is_owner

no_cache = 1
sitemap = 0


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=%2Fsite-work"
        raise frappe.Redirect
    require_site_user()
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.display_name = frappe.get_cached_value("User", frappe.session.user, "full_name")
    context.is_owner = is_owner()
