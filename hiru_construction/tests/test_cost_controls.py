"""Explicit fixtures on hiru-test.localhost; no upstream accounting test bootstrap."""
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from hiru_construction.construction.report.construction_project_costs.construction_project_costs import (
    execute, read_ledger_and_orders,
)


class TestCostControls(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.get("hiru_test"):
            raise RuntimeError("Cost-control tests require the separate marked test site. Use make test.")
        super().setUpClass()
        cls.company = frappe.get_doc("Company", "Cost Controls Test")
        cls.expense = cls.company.default_expense_account
        cls.cash = frappe.get_all("Account", filters={"company": cls.company.name,
            "account_type": "Cash", "is_group": 0}, pluck="name")[0]
        cls.other_expense = frappe.get_doc({"doctype": "Account", "account_name": "Unplanned Costs",
            "company": cls.company.name, "root_type": "Expense", "is_group": 0,
            "parent_account": frappe.db.get_value("Account", cls.expense, "parent_account")}).insert().name
        cls.category = frappe.get_all("Construction Cost Category", filters={"scope": "Global"}, pluck="name")[0]
        year = int(nowdate()[:4])
        if not frappe.db.exists("Fiscal Year", str(year)):
            frappe.get_doc({"doctype": "Fiscal Year", "year": str(year),
                "year_start_date": f"{year}-01-01", "year_end_date": f"{year}-12-31"}).insert()
        cls.supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Cost Controls Supplier",
            "supplier_group": "All Supplier Groups", "supplier_type": "Company"}).insert().name
        if not frappe.db.exists("UOM", "Nos"):
            frappe.get_doc({"doctype": "UOM", "uom_name": "Nos"}).insert()
        cls.item = frappe.get_doc({"doctype": "Item", "item_code": "COST-CONTROLS-SERVICE",
            "item_name": "Cost controls service", "item_group": "All Item Groups", "is_stock_item": 0,
            "stock_uom": "Nos", "item_defaults": [{"company": cls.company.name,
                "expense_account": cls.expense, "buying_cost_center": cls.company.cost_center}]}).insert().name

    def setUp(self):
        super().setUp()
        self.project = frappe.get_doc({"doctype": "Project", "project_name": frappe.generate_hash(length=12),
            "company": self.company.name}).insert()

    def plan(self, baseline=None, **kwargs):
        return frappe.get_doc({"doctype": "Construction Cost Plan", "plan_name": frappe.generate_hash(length=12),
            "project": self.project.name, "version_kind": "Approved revision" if baseline else "Tender baseline",
            "baseline": baseline.name if baseline else None, "items": [{"category": self.category,
                "account": self.expense, "original_estimate": 1000,
                "approved_revision": 1500 if baseline else 0, "contingency": 100}], **kwargs})

    def test_approval_cancellation_and_immutable_tender(self):
        baseline = self.plan().insert().submit()
        revision1 = self.plan(baseline).insert().submit()
        revision2 = self.plan(baseline).insert().submit()
        self.assertEqual(revision2.revision_number, 2)
        self.assertEqual(revision1.reload().status, "Superseded")
        revision2.cancel()
        self.assertEqual(revision1.reload().status, "Approved")
        self.assertEqual(revision2.reload().status, "Cancelled")
        with self.assertRaises(frappe.ValidationError):
            baseline.cancel()
        baseline.reload()
        baseline.items[0].original_estimate = 20
        with self.assertRaises(frappe.ValidationError):
            baseline.save()

    def test_baseline_duplicate_and_revision_original_validation(self):
        baseline = self.plan().insert().submit()
        with self.assertRaises(frappe.ValidationError):
            self.plan().insert().submit()
        revision = self.plan(baseline)
        revision.items[0].original_estimate = 999
        with self.assertRaises(frappe.ValidationError):
            revision.insert()
        missing = self.plan(version_kind="Approved revision")
        with self.assertRaises(frappe.ValidationError):
            missing.insert()

    def test_duplicate_account_and_wrong_category_scope(self):
        plan = self.plan()
        plan.append("items", {"category": self.category, "account": self.expense, "original_estimate": 50})
        with self.assertRaises(frappe.ValidationError):
            plan.insert()
        other_project = frappe.get_doc({"doctype": "Project", "project_name": frappe.generate_hash(length=12),
            "company": self.company.name}).insert()
        category = frappe.get_doc({"doctype": "Construction Cost Category", "category_name": "Local",
            "scope": "Project", "project": other_project.name}).insert()
        plan = self.plan()
        plan.items[0].category = category.name
        with self.assertRaises(frappe.ValidationError):
            plan.insert()

    def test_asset_and_group_accounts_rejected(self):
        for account in (self.cash, frappe.db.get_value("Account", self.expense, "parent_account")):
            plan = self.plan()
            plan.items[0].account = account
            with self.assertRaises(frappe.ValidationError):
                plan.insert()

    def test_accounts_from_another_company_rejected(self):
        other = frappe.get_doc({"doctype": "Company", "company_name": "Other Cost Test",
            "abbr": "OCT", "country": "Sri Lanka", "default_currency": "LKR",
            "chart_of_accounts": "Standard"}).insert()
        plan = self.plan()
        plan.items[0].account = other.default_expense_account
        with self.assertRaises(frappe.ValidationError):
            plan.insert()

    def test_used_category_scope_is_preserved(self):
        self.plan().insert().submit()
        category = frappe.get_doc("Construction Cost Category", self.category)
        category.scope = "Project"
        category.project = self.project.name
        with self.assertRaises(frappe.ValidationError):
            category.save()

    def journal(self, account, amount):
        return frappe.get_doc({"doctype": "Journal Entry", "voucher_type": "Journal Entry",
            "company": self.company.name, "posting_date": nowdate(), "accounts": [
                {"account": account, "project": self.project.name,
                 "cost_center": self.company.cost_center, "debit_in_account_currency": amount},
                {"account": self.cash, "cost_center": self.company.cost_center,
                 "credit_in_account_currency": amount}]}).insert().submit()

    def order(self, currency="LKR", conversion_rate=1):
        return frappe.get_doc({"doctype": "Purchase Order", "company": self.company.name,
            "supplier": self.supplier, "transaction_date": nowdate(), "schedule_date": nowdate(),
            "currency": currency, "conversion_rate": conversion_rate, "project": self.project.name,
            "items": [{"item_code": self.item, "qty": 10, "rate": 100, "schedule_date": nowdate(),
                "expense_account": self.expense, "cost_center": self.company.cost_center,
                "project": self.project.name}]}).insert().submit()

    def test_report_zero_revision_and_unmapped_costs(self):
        baseline = self.plan().insert().submit()
        revision = self.plan(baseline)
        revision.items[0].approved_revision = 0
        revision.insert().submit()
        self.journal(self.expense, 120)
        self.journal(self.other_expense, 30)
        cancelled = self.journal(self.expense, 70)
        cancelled.cancel()
        closing = self.journal(self.expense, 80)
        frappe.db.set_value("GL Entry", {"voucher_no": closing.name}, "voucher_type", "Period Closing Voucher")
        rows = execute({"project": self.project.name})[1]
        mapped = next(row for row in rows if row["account"] == self.expense)
        unmapped = next(row for row in rows if row["account"] == self.other_expense)
        self.assertEqual(mapped["current_budget"], 0)
        self.assertEqual(mapped["original_budget"], 1000)
        self.assertEqual(mapped["remaining_budget"], -120)
        self.assertEqual(unmapped["category"], "Unmapped")
        self.assertEqual(unmapped["actual"], 30)

    def test_order_invoice_and_cancellation_do_not_double_count(self):
        from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice
        self.plan().insert().submit()
        order = self.order()
        invoice = make_purchase_invoice(order.name)
        invoice.items[0].qty = 4
        invoice.insert().submit()
        rows = execute({"project": self.project.name})[1]
        row = next(row for row in rows if row["account"] == self.expense)
        self.assertEqual((row["actual"], row["commitment"], row["exposure"]), (400, 600, 1000))
        invoice.cancel()
        actuals, commitments, _ = read_ledger_and_orders(self.project.name, self.company.name)
        self.assertEqual(actuals.get(self.expense, 0), 0)
        self.assertEqual(commitments[self.expense], 1000)
        order.reload().cancel()
        self.assertEqual(dict(read_ledger_and_orders(self.project.name, self.company.name)[1]), {})

    def test_foreign_currency_commitment_uses_company_currency(self):
        order = self.order(currency="USD", conversion_rate=300)
        # Exercise the same billing ratio used by ERPNext, including a header discount.
        item = order.items[0]
        frappe.db.set_value("Purchase Order Item", item.name, {"billed_amt": 400, "base_net_amount": 270000})
        self.assertEqual(read_ledger_and_orders(self.project.name, self.company.name)[1][self.expense], 162000)

    def test_unbilled_receipts_require_reconciliation(self):
        self.plan().insert().submit()
        order = self.order()
        frappe.db.set_value("Purchase Order Item", order.items[0].name, "received_qty", 5)
        result = execute({"project": self.project.name})
        row = next(row for row in result[1] if row["account"] == self.expense)
        self.assertEqual(row["commitment"], 1000)
        self.assertIsNone(row["exposure"])
        self.assertIsNone(row["remaining_budget"])
        self.assertEqual(result[4][-1]["value"], "Review receipts")

    def test_closed_orders_no_longer_commit_budget(self):
        order = self.order()
        frappe.db.set_value("Purchase Order", order.name, "status", "Closed")
        self.assertEqual(dict(read_ledger_and_orders(self.project.name, self.company.name)[1]), {})

    def test_guest_cannot_read_aggregate_costs(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                execute({"project": self.project.name})
        finally:
            frappe.set_user("Administrator")
