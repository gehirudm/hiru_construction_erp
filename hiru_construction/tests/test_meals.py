from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, add_days

from hiru_construction.daily import save_expense, post_expense, overview
from hiru_construction.meals import board, save_rates, save_meal, summary, alerts


class TestMeals(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.get("hiru_test"):
            raise RuntimeError("Meal tests require the isolated test site")
        super().setUpClass()
        cls.company = frappe.get_doc("Company", "Cost Controls Test")

    def setUp(self):
        super().setUp()
        suffix = str(uuid4())[:8]
        self.project = frappe.get_doc({"doctype": "Project", "project_name": "Meals " + suffix,
            "company": self.company.name, "cost_center": self.company.cost_center}).insert()
        self.category = frappe.db.get_value("Construction Cost Category", {"category_name": "Meals", "scope": "Global"}, "name")
        frappe.get_doc({"doctype": "Construction Cost Plan", "plan_name": "Meals " + suffix,
            "project": self.project.name, "version_kind": "Tender baseline", "items": [{"category": self.category,
                "account": self.company.default_expense_account, "original_estimate": 10000}]}).insert().submit()
        self.supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Meals " + suffix,
            "supplier_group": "All Supplier Groups", "supplier_type": "Company"}).insert()
        self.attendance = []
        for status in ("Present", "Half Day", "Absent"):
            employee = frappe.get_doc({"doctype": "Employee", "first_name": status + suffix, "gender": "Male",
                "date_of_birth": "1990-01-01", "date_of_joining": add_days(nowdate(), -20),
                "company": self.company.name, "status": "Active", "custom_construction_project": self.project.name}).insert()
            self.attendance.append(frappe.get_doc({"doctype": "Attendance", "employee": employee.name,
                "company": self.company.name, "attendance_date": nowdate(), "status": status,
                "custom_construction_project": self.project.name}).insert().submit())
        save_rates(self.project.name, {"Lunch": 250})

    def meal(self, **changes):
        args = {"project": self.project.name, "date": nowdate(), "meal_type": "Lunch", "diners": 2, **changes}
        return save_meal(**args)

    def bill(self, meal_record, amount, **changes):
        return save_expense({"request_id": str(uuid4()), "project": self.project.name,
            "account": self.company.default_expense_account, "supplier": self.supplier.name,
            "description": "Lunch", "amount": amount, "date": nowdate(), "meal": meal_record["name"], **changes})

    def test_attendance_suggestion_and_historical_snapshots(self):
        self.assertEqual(board(self.project.name)["suggested_diners"], 2)
        meal = self.meal()
        self.assertEqual(self.meal()["name"], meal["name"])
        save_rates(self.project.name, {"Lunch": 300})
        self.attendance[0].cancel()
        current = board(self.project.name)
        self.assertEqual(current["suggested_diners"], 1)
        self.assertEqual(current["meals"][0]["attendance_headcount"], 2)
        self.assertEqual(current["meals"][0]["expected"], 250)
        doc = frappe.get_doc("Construction Meal", meal["name"])
        doc.expected_per_head = 300
        with self.assertRaises(frappe.ValidationError):
            doc.save()

    def test_multiple_bills_alerts_retry_and_cancellation(self):
        meal = self.meal()
        first = self.bill(meal, 300)
        self.assertEqual(summary(frappe.get_doc("Construction Meal", meal["name"]))["total"], 0)
        post_expense(first["name"], first["modified"])
        second = self.bill(meal, 250)
        post_expense(second["name"], second["modified"])
        post_expense(second["name"], second["modified"])
        data = summary(frappe.get_doc("Construction Meal", meal["name"]))
        self.assertEqual((data["total"], data["diners"], data["per_head"]), (550, 2, 275))
        self.assertEqual(overview(self.project.name)["spent"], 550)
        self.assertEqual(len(alerts(self.project.name)), 1)
        self.assertEqual(frappe.db.count("Notification Log", {"document_name": meal["name"]}), 1)
        from frappe.desk.doctype.notification_log.notification_log import get_skip_email_types
        self.assertIn("Construction Meal Alert", get_skip_email_types())
        frappe.get_doc("Purchase Invoice", second["name"]).cancel()
        self.assertEqual(len(alerts(self.project.name)), 0)
        self.assertEqual(summary(frappe.get_doc("Construction Meal", meal["name"]))["total"], 300)

    def test_adjustment_reason_and_stale_headcount(self):
        with self.assertRaises(frappe.ValidationError):
            self.meal(diners=1)
        meal = self.meal()
        bill = self.bill(meal, 300)
        post_expense(bill["name"], bill["modified"])
        updated = self.meal(diners=1, reason="One worker did not eat", name=meal["name"], modified=meal["modified"])
        self.assertTrue(updated["over_limit"])
        with self.assertRaises(frappe.ValidationError):
            self.meal(diners=2, reason="Correction", name=meal["name"], modified=meal["modified"])

    def test_missing_attendance_and_invalid_counts(self):
        for count in (0, -1, 1.5, "NaN"):
            with self.assertRaises(frappe.ValidationError):
                self.meal(diners=count)
        with self.assertRaises(frappe.ValidationError):
            self.meal(date=add_days(nowdate(), -1))
        manual = self.meal(date=add_days(nowdate(), -1), reason="Attendance not entered; checked actual diners")
        self.assertEqual(manual["attendance_headcount"], 0)

    def test_meal_expense_date_and_required_link(self):
        meal = self.meal()
        for changes in ({"meal": ""}, {"date": add_days(nowdate(), -1)}):
            with self.assertRaises(frappe.ValidationError):
                self.bill(meal, 100, **changes)

    def test_guest_cannot_change_rates_or_meals(self):
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                save_rates(self.project.name, {"Lunch": 250})
            with self.assertRaises(frappe.PermissionError):
                self.meal()
            with self.assertRaises(frappe.PermissionError):
                board(self.project.name)
        finally:
            frappe.set_user("Administrator")

    def test_advanced_rate_settings_reject_duplicates_and_negative_values(self):
        project = frappe.get_doc("Project", self.project.name)
        project.append("custom_construction_meal_rates", {"meal_type": "Lunch", "expected_per_head": 100})
        with self.assertRaises(frappe.ValidationError):
            project.save()
        project = frappe.get_doc("Project", self.project.name)
        project.custom_construction_meal_rates[0].expected_per_head = -1
        with self.assertRaises(frappe.ValidationError):
            project.save()
