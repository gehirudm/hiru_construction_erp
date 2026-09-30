"""Project-scoped portal access and API-only, auditable site records."""
from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe import _
from frappe.model.document import Document

_writing = ContextVar("site_service_write", default=False)


@contextmanager
def service_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


def is_owner(user=None):
    user = user or frappe.session.user
    return user != "Guest" and (user == "Administrator" or "System Manager" in frappe.get_roles(user))


def require_owner():
    if not is_owner():
        frappe.throw(_("Only the owner can manage access, money and approvals."), frappe.PermissionError)


def require_site_user():
    if not is_owner() and (frappe.session.user == "Guest" or "Construction Supervisor" not in frappe.get_roles()):
        frappe.throw(_("You do not have site access."), frappe.PermissionError)


def wallet_access(name, lock=False, active=True):
    require_site_user()
    if lock:
        frappe.db.sql("select name from `tabConstruction Site Wallet` where name=%s for update", name)
    doc = frappe.get_doc("Construction Site Wallet", name)
    if not is_owner() and (doc.supervisor != frappe.session.user or not doc.enabled):
        frappe.throw(_("This site is not assigned to you."), frappe.PermissionError)
    if active and not doc.enabled:
        frappe.throw(_("This site assignment has been disabled."))
    return doc


class ProtectedSiteDocument(Document):
    def validate(self):
        if not _writing.get():
            frappe.throw(_("Use Site team & money to submit or correct this record."), frappe.PermissionError)

    def on_trash(self):
        frappe.throw(_("Site history cannot be deleted. Use the review or reversal action."), frappe.PermissionError)


def wallet_query(user=None):
    user = user or frappe.session.user
    if is_owner(user):
        return ""
    if user == "Guest" or "Construction Supervisor" not in frappe.get_roles(user):
        return "1=0"
    return "`tabConstruction Site Wallet`.enabled=1 and `tabConstruction Site Wallet`.supervisor=" + frappe.db.escape(user)


def entry_query(user=None):
    user = user or frappe.session.user
    if is_owner(user):
        return ""
    if user == "Guest" or "Construction Supervisor" not in frappe.get_roles(user):
        return "1=0"
    return ("`tabConstruction Site Entry`.wallet in (select name from `tabConstruction Site Wallet` "
            "where enabled=1 and supervisor=" + frappe.db.escape(user) + ")")


def document_permission(doc, user=None, permission_type=None):
    user = user or frappe.session.user
    if permission_type not in (None, "read", "select", "report", "print"):
        return False
    if is_owner(user):
        return True
    if user == "Guest" or "Construction Supervisor" not in frappe.get_roles(user):
        return False
    wallet = doc if doc.doctype == "Construction Site Wallet" else frappe.get_doc("Construction Site Wallet", doc.wallet)
    return bool(wallet.enabled and wallet.supervisor == user)


def protect_voucher(doc, method=None):
    if not _writing.get() and frappe.db.exists("Construction Site Entry", {"voucher_type": doc.doctype, "voucher": doc.name}):
        frappe.throw(_("This record belongs to a site submission. Use Site team & money for an audited correction or reversal."), frappe.PermissionError)


def setup():
    if not frappe.db.exists("Role", "Construction Supervisor"):
        frappe.get_doc({"doctype": "Role", "role_name": "Construction Supervisor", "desk_access": 0}).insert(ignore_permissions=True)
    elif frappe.db.get_value("Role", "Construction Supervisor", "desk_access"):
        role = frappe.get_doc("Role", "Construction Supervisor")
        role.desk_access = 0
        role.save(ignore_permissions=True)
