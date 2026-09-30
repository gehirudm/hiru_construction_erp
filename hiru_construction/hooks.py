app_name = "hiru_construction"
app_title = "Hiru Construction"
app_publisher = "Hiru Construction"
app_description = "Construction project management for ERPNext"
app_email = ""
app_license = "Proprietary"
required_apps = ["erpnext", "hrms"]
after_install = "hiru_construction.setup.after_install"
before_migrate = "hiru_construction.site_access.setup"
permission_query_conditions = {
    "Construction Site Wallet": "hiru_construction.site_access.wallet_query",
    "Construction Site Entry": "hiru_construction.site_access.entry_query",
}
has_permission = {
    "Construction Site Wallet": "hiru_construction.site_access.document_permission",
    "Construction Site Entry": "hiru_construction.site_access.document_permission",
}
get_website_user_home_page = "hiru_construction.daily.home_page"
notification_skip_email_types = ["Construction Meal Alert"]
doc_events = {"Purchase Invoice": {
    "validate": ["hiru_construction.fuel.validate_invoice", "hiru_construction.meals.validate_invoice"],
    "on_submit": "hiru_construction.meals.invoice_changed", "on_cancel": "hiru_construction.meals.invoice_changed",
    "before_cancel": "hiru_construction.site_access.protect_voucher",
    "before_update_after_submit": "hiru_construction.site_access.protect_voucher",
    "on_trash": "hiru_construction.site_access.protect_voucher"},
    "Attendance": {"before_cancel": "hiru_construction.site_access.protect_voucher", "before_update_after_submit": "hiru_construction.site_access.protect_voucher", "on_trash": "hiru_construction.site_access.protect_voucher"},
    "Journal Entry": {"before_cancel": "hiru_construction.site_access.protect_voucher", "before_update_after_submit": "hiru_construction.site_access.protect_voucher", "on_trash": "hiru_construction.site_access.protect_voucher"},
    "Project": {"validate": "hiru_construction.meals.validate_rates"}}
