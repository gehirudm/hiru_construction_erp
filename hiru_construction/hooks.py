app_name = "hiru_construction"
app_title = "Hiru Construction"
app_publisher = "Hiru Construction"
app_description = "Construction project management for ERPNext"
app_email = ""
app_license = "Proprietary"
required_apps = ["erpnext", "hrms"]
after_install = "hiru_construction.setup.after_install"
get_website_user_home_page = "hiru_construction.daily.home_page"
notification_skip_email_types = ["Construction Meal Alert"]
doc_events = {"Purchase Invoice": {
    "validate": ["hiru_construction.fuel.validate_invoice", "hiru_construction.meals.validate_invoice"],
    "on_submit": "hiru_construction.meals.invoice_changed", "on_cancel": "hiru_construction.meals.invoice_changed"},
    "Project": {"validate": "hiru_construction.meals.validate_rates"}}
