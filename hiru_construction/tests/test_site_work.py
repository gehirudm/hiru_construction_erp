from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, add_days

from hiru_construction.daily import save_expense, post_expense, overview
from hiru_construction.site_work import save_attendance, crew, category_detail, assign_workers


class TestSiteWork(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.get("hiru_test"):
            raise RuntimeError("Use the isolated test site")
        super().setUpClass()
        cls.company = frappe.get_doc("Company", "Cost Controls Test")

    def setUp(self):
        super().setUp()
        suffix = str(uuid4())[:8]
        self.project = frappe.get_doc({"doctype": "Project", "project_name": "Site " + suffix,
            "company": self.company.name, "cost_center": self.company.cost_center}).insert()
        self.category = frappe.get_doc({"doctype": "Construction Cost Category", "category_name": "Fuel " + suffix,
            "scope": "Global", "entry_type": "Fuel"}).insert()
        frappe.get_doc({"doctype": "Construction Cost Plan", "plan_name": "Site " + suffix,
            "project": self.project.name, "version_kind": "Tender baseline", "items": [{
                "category": self.category.name, "account": self.company.default_expense_account,
                "original_estimate": 10000}]}).insert().submit()
        self.worker = frappe.get_doc({"doctype": "Employee", "first_name": "Site " + suffix,
            "gender": "Male", "date_of_birth": "1990-01-01", "date_of_joining": add_days(nowdate(), -30),
            "company": self.company.name, "status": "Active", "custom_construction_project": self.project.name}).insert()
        self.vehicle = frappe.get_doc({"doctype": "Vehicle", "license_plate": "SITE-" + suffix,
            "make": "Test", "model": "Truck", "last_odometer": 100, "fuel_type": "Diesel",
            "uom": "Litre", "company": self.company.name}).insert()
        self.supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Fuel " + suffix,
            "supplier_group": "All Supplier Groups", "supplier_type": "Company"}).insert()

    def attendance(self, **changes):
        return {"employee": self.worker.name, "status": "Present", "regular": 8, "ot": 2, **changes}

    def fuel(self, **changes):
        return {"request_id": str(uuid4()), "project": self.project.name,
            "account": self.company.default_expense_account, "supplier": self.supplier.name,
            "description": "Diesel", "amount": "123.45", "date": nowdate(),
            "vehicle": self.vehicle.name, "litres": "10", "meter": "120", **changes}

    def test_attendance_draft_confirm_retry_and_native_hours(self):
        row = self.attendance()
        result = save_attendance(self.project.name, nowdate(), [row])
        record = frappe.get_doc("Attendance", result["saved"] and crew(self.project.name)["employees"][0]["attendance"]["name"])
        self.assertEqual(record.docstatus, 0)
        self.assertEqual(record.working_hours, 10)
        self.assertEqual(record.actual_overtime_duration, 2)
        save_attendance(self.project.name, nowdate(), [row], True)
        save_attendance(self.project.name, nowdate(), [row], True)
        self.assertEqual(frappe.db.count("Attendance", {"employee": self.worker.name}), 1)
        self.assertEqual(crew(self.project.name)["ot_total"], 2)
        with self.assertRaises(frappe.ValidationError):
            save_attendance(self.project.name, nowdate(), [self.attendance(ot=3)], True)

    def test_attendance_invalid_hours_future_and_stale_draft(self):
        for changes in ({"ot": -1}, {"ot": "NaN"}, {"regular": 23, "ot": 2}, {"status": "Absent", "regular": 0, "ot": 2}):
            with self.assertRaises(frappe.ValidationError):
                save_attendance(self.project.name, nowdate(), [self.attendance(**changes)])
        with self.assertRaises(frappe.ValidationError):
            save_attendance(self.project.name, add_days(nowdate(), 1), [self.attendance()])
        save_attendance(self.project.name, nowdate(), [self.attendance()])
        with self.assertRaises(frappe.ValidationError):
            save_attendance(self.project.name, nowdate(), [self.attendance(regular=7)])

    def test_draft_can_be_corrected_with_version(self):
        save_attendance(self.project.name, nowdate(), [self.attendance()])
        a = crew(self.project.name)["employees"][0]["attendance"]
        save_attendance(self.project.name, nowdate(), [self.attendance(status="Half Day", regular=4, ot=0,
            name=a.name, modified=str(a.modified))], True)
        self.assertEqual(frappe.get_doc("Attendance", a.name).status, "Half Day")

    def test_wrong_project_worker_and_guest_denied(self):
        self.worker.custom_construction_project = None
        self.worker.save()
        with self.assertRaises(frappe.ValidationError):
            save_attendance(self.project.name, nowdate(), [self.attendance()])
        assign_workers(self.project.name, [self.worker.name])
        frappe.set_user("Guest")
        try:
            with self.assertRaises(frappe.PermissionError):
                save_attendance(self.project.name, nowdate(), [self.attendance()])
            with self.assertRaises(frappe.PermissionError):
                category_detail(self.project.name, self.category.name)
        finally:
            frappe.set_user("Administrator")

    def test_fuel_posts_once_with_equipment_and_category_drilldown(self):
        payload = self.fuel()
        draft = save_expense(payload)
        self.assertEqual(draft["vehicle"], self.vehicle.name)
        self.assertEqual(overview(self.project.name)["spent"], 0)
        self.assertEqual(save_expense(payload)["name"], draft["name"])
        post_expense(draft["name"], draft["modified"])
        post_expense(draft["name"], draft["modified"])
        detail = category_detail(self.project.name, self.category.name)
        self.assertEqual(detail["spent"], 123.45)
        self.assertEqual(len(detail["entries"]), 1)
        self.assertEqual(frappe.db.count("Vehicle Log", {"license_plate": self.vehicle.name}), 0)

    def test_fuel_requires_equipment_litres_and_valid_meter(self):
        for changes in ({"vehicle": ""}, {"litres": "0"}, {"meter": ""}, {"meter": "bad"}, {"meter": "90"}):
            with self.assertRaises(frappe.ValidationError):
                save_expense(self.fuel(**changes))
        self.vehicle.company = None
        self.vehicle.save()
        with self.assertRaises(frappe.ValidationError):
            save_expense(self.fuel())

    def test_fuel_draft_revalidated_against_newer_reading(self):
        old = save_expense(self.fuel(meter="120"))
        newer = save_expense(self.fuel(meter="140"))
        post_expense(newer["name"], newer["modified"])
        with self.assertRaises(frappe.ValidationError):
            post_expense(old["name"], old["modified"])
        with self.assertRaises(frappe.ValidationError):
            save_expense(self.fuel(meter="150", date=add_days(nowdate(), -1)))

    def test_machine_fuel_uses_asset_engine_hours(self):
        suffix = str(uuid4())[:8]
        fixed = frappe.get_all("Account", filters={"company": self.company.name,
            "account_type": "Fixed Asset", "is_group": 0}, pluck="name")[0]
        category = frappe.get_doc({"doctype": "Asset Category", "asset_category_name": "Machines " + suffix,
            "accounts": [{"company_name": self.company.name, "fixed_asset_account": fixed}]}).insert()
        item = frappe.get_doc({"doctype": "Item", "item_code": "Machine " + suffix, "item_group": "All Item Groups",
            "stock_uom": "Nos", "is_stock_item": 0, "is_fixed_asset": 1, "asset_category": category.name}).insert()
        location = frappe.get_doc({"doctype": "Location", "location_name": "Site " + suffix}).insert()
        asset = frappe.get_doc({"doctype": "Asset", "asset_name": "Mixer " + suffix, "item_code": item.name,
            "company": self.company.name, "location": location.name, "purchase_date": nowdate(),
            "available_for_use_date": nowdate(), "asset_type": "Existing Asset", "asset_quantity": 1,
            "net_purchase_amount": 10000, "purchase_amount": 10000, "calculate_depreciation": 0}).insert()
        with self.assertRaises(frappe.ValidationError):
            save_expense(self.fuel(machine=asset.name))
        draft = save_expense(self.fuel(vehicle="", machine=asset.name, meter="125.25"))
        post_expense(draft["name"], draft["modified"])
        self.assertEqual(draft["machine"], asset.name)
        self.assertEqual(draft["meter"], 125.25)
        unmetered = save_expense(self.fuel(vehicle="", machine=asset.name, meter=""))
        self.assertIsNone(unmetered["meter"])
        post_expense(unmetered["name"], unmetered["modified"])
        with self.assertRaises(frappe.ValidationError):
            save_expense(self.fuel(vehicle="", machine=asset.name, meter="124"))
