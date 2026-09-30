import frappe
from frappe.tests import IntegrationTestCase

from hiru_construction.expenses import assemble


class TestExpenseRows(IntegrationTestCase):
    def test_split_documents_credits_unmapped_and_decimal_totals(self):
        entries = [frappe._dict(name=str(i), posting_date="2026-09-01", creation=str(i),
            voucher_type="Journal Entry", voucher_no=voucher, account=account, party=None,
            remarks="<b>Site cost</b>", debit=debit, credit=credit)
            for i, (voucher, account, debit, credit) in enumerate([
                ("A", "materials", "0.10", 0), ("A", "materials", "0.20", 0),
                ("A", "labour", "10", 0), ("B", "materials", 0, "0.05"),
                ("C", "other", "3", 0)])]
        mapping = {"materials": ("cat-1", "Materials"), "labour": ("cat-2", "Labour")}
        rows, total, _, _ = assemble(entries, mapping, {}, {})
        self.assertEqual([r["amount"] for r in rows], [0.3, 10, -0.05, 3])
        self.assertEqual(rows[-1]["running_total"], 13.25)
        self.assertEqual(total, 13.25)
        self.assertEqual(rows[-1]["category_label"], "Unmapped")
        selected, total, _, _ = assemble(entries, mapping, {}, {"category": "cat-1"})
        self.assertEqual([r["running_total"] for r in selected], [0.3, 0.25])
        self.assertEqual(total, 0.25)
        self.assertEqual(rows[0]["description"], "Site cost")
