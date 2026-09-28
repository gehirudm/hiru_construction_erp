from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from hiru_construction.daily import overview, save_expense, post_expense, expense


class TestDailyWork(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.get("hiru_test"):
            raise RuntimeError("Use make test on the isolated site")
        super().setUpClass()
        cls.company = frappe.get_doc("Company", "Cost Controls Test")
        cls.category = frappe.get_all("Construction Cost Category", filters={"scope": "Global", "category_name": "Transport"}, pluck="name")[0]
        cls.supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Daily Supplier",
            "supplier_group": "All Supplier Groups", "supplier_type": "Company"}).insert().name
        cls.cash = frappe.get_all("Account", filters={"company": cls.company.name,
            "account_type": "Cash", "is_group": 0}, pluck="name")[0]

    def setUp(self):
        super().setUp()
        self.project = frappe.get_doc({"doctype": "Project", "project_name": "Daily " + str(uuid4()),
            "company": self.company.name, "cost_center": self.company.cost_center}).insert()
        frappe.get_doc({"doctype": "Construction Cost Plan", "plan_name": "Daily " + str(uuid4()),
            "project": self.project.name, "version_kind": "Tender baseline", "items": [{
                "category": self.category, "account": self.company.default_expense_account,
                "original_estimate": 10000}]}).insert().submit()

    def payload(self, **changes):
        return {"request_id": str(uuid4()), "project": self.project.name,
            "account": self.company.default_expense_account, "supplier": self.supplier,
            "description": "Site delivery", "amount": "250.00", "date": nowdate(), **changes}

    def test_draft_review_post_and_retry_do_not_duplicate_cost(self):
        payload = self.payload(amount="250.25")
        draft = save_expense(payload)
        self.assertEqual(draft["docstatus"], 0)
        self.assertEqual(frappe.db.count("GL Entry", {"voucher_no": draft["name"]}), 0)
        self.assertEqual(save_expense(payload)["name"], draft["name"])
        result = post_expense(draft["name"], draft["modified"])
        self.assertEqual(result["docstatus"], 1)
        count = frappe.db.count("GL Entry", {"voucher_no": draft["name"]})
        post_expense(draft["name"], draft["modified"])
        self.assertEqual(frappe.db.count("GL Entry", {"voucher_no": draft["name"]}), count)
        self.assertEqual(overview(self.project.name)["spent"], 250.25)
        self.assertEqual(frappe.get_doc("Purchase Invoice", draft["name"]).outstanding_amount, 250.25)

    def test_already_paid_expense_posts_cash_and_clears_payable(self):
        draft = save_expense(self.payload(paid_from=self.cash, amount="250.25"))
        post_expense(draft["name"], draft["modified"])
        invoice = frappe.get_doc("Purchase Invoice", draft["name"])
        self.assertEqual(invoice.outstanding_amount, 0)
        amount = frappe.db.sql("""select sum(credit-debit) from `tabGL Entry`
            where voucher_no=%s and account=%s and is_cancelled=0""", (invoice.name, self.cash))[0][0]
        self.assertEqual(float(amount), 250.25)
        self.assertEqual(overview(self.project.name)["spent"], 250.25)

    def test_changed_retry_payload_is_rejected(self):
        payload = self.payload()
        save_expense(payload)
        payload["amount"] = "500"
        with self.assertRaises(frappe.ValidationError):
            save_expense(payload)

    def test_stale_review_cannot_post_changed_draft(self):
        draft = save_expense(self.payload())
        invoice = frappe.get_doc("Purchase Invoice", draft["name"])
        invoice.items[0].rate = 450
        invoice.save()
        with self.assertRaises(frappe.ValidationError):
            post_expense(draft["name"], draft["modified"])

    def test_invalid_amounts_and_unmapped_accounts_rejected(self):
        for amount in ("-1", "0", "NaN", "Infinity", "1.001", "bad"):
            with self.assertRaises(frappe.ValidationError):
                save_expense(self.payload(amount=amount))
        with self.assertRaises(frappe.ValidationError):
            save_expense(self.payload(account=self.cash))
        with self.assertRaises(frappe.ValidationError):
            save_expense(self.payload(paid_from=self.company.default_expense_account))

    def test_guest_cannot_read_or_write(self):
        draft = save_expense(self.payload())
        frappe.set_user("Guest")
        try:
            for action in (lambda: overview(self.project.name), lambda: expense(draft["name"]),
                           lambda: post_expense(draft["name"], draft["modified"]), lambda: save_expense(self.payload())):
                with self.assertRaises(frappe.PermissionError):
                    action()
        finally:
            frappe.set_user("Administrator")

    def test_project_manager_without_accounting_permissions_cannot_create(self):
        user = frappe.get_doc({"doctype": "User", "email": "daily-manager@example.test",
            "first_name": "Daily Manager", "send_welcome_email": 0,
            "roles": [{"role": "Projects Manager"}]}).insert()
        frappe.set_user(user.name)
        try:
            with self.assertRaises(frappe.PermissionError):
                save_expense(self.payload())
        finally:
            frappe.set_user("Administrator")
