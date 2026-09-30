from uuid import uuid4

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate, add_days

from hiru_construction import site_team as team
from hiru_construction.daily import overview


class TestSiteTeam(IntegrationTestCase):
    @classmethod
    def setUpClass(cls):
        if not frappe.conf.get("hiru_test"):
            raise RuntimeError("Use the isolated test site")
        super().setUpClass()
        cls.company = frappe.get_doc("Company", "Cost Controls Test")
        cls.category = frappe.db.get_value("Construction Cost Category", {"scope": "Global", "category_name": "Transport"}, "name")
        cls.supplier = frappe.get_doc({"doctype": "Supplier", "supplier_name": "Team Supplier " + str(uuid4())[:8],
            "supplier_group": "All Supplier Groups", "supplier_type": "Company"}).insert().name
        cls.cash = frappe.get_all("Account", filters={"company": cls.company.name, "account_type": "Cash", "is_group": 0}, pluck="name")[0]

    def setUp(self):
        super().setUp()
        frappe.set_user("Administrator")
        suffix = str(uuid4())[:8]
        self.project = frappe.get_doc({"doctype": "Project", "project_name": "Team " + suffix,
            "company": self.company.name, "cost_center": self.company.cost_center}).insert()
        frappe.get_doc({"doctype": "Construction Cost Plan", "plan_name": "Team " + suffix,
            "project": self.project.name, "version_kind": "Tender baseline", "items": [{"category": self.category,
                "account": self.company.default_expense_account, "original_estimate": 10000}]}).insert().submit()
        self.user = frappe.get_doc({"doctype": "User", "email": f"team-{suffix}@example.test", "first_name": "Supervisor",
            "send_welcome_email": 0, "user_type": "Website User", "roles": [{"role": "Construction Supervisor"}]}).insert().name
        self.wallet = team.assign(self.project.name, self.user)["wallet"]
        self.worker = frappe.get_doc({"doctype": "Employee", "first_name": "Team Worker " + suffix, "gender": "Male",
            "date_of_birth": "1990-01-01", "date_of_joining": add_days(nowdate(), -30), "company": self.company.name,
            "status": "Active", "custom_construction_project": self.project.name}).insert().name

    def tearDown(self):
        frappe.set_user("Administrator")
        super().tearDown()

    def expense(self, **changes):
        return {"date": nowdate(), "category": self.category, "supplier": self.supplier,
            "amount": 125, "description": "Delivery paid on site", **changes}

    def mark(self, **changes):
        return {"date": nowdate(), "employee": self.worker, "status": "Present", "regular": 8, "ot": 2, **changes}

    def submit(self, kind="Expense", payload=None, revision=None, key=None):
        return team.submit_entry(self.wallet, kind, payload or self.expense(), key or str(uuid4()), revision)["name"]

    def fund(self, amount=100, kind="Funding", key=None):
        return team.transfer(self.wallet, kind, amount, nowdate(), self.cash, "Cash handed over", key or str(uuid4()))["name"]

    def test_cash_custody_negative_balance_and_no_double_count(self):
        funding = self.fund()
        self.assertEqual(overview(self.project.name)["spent"], 0)
        frappe.set_user(self.user)
        name = self.submit()
        self.assertEqual(team.details(self.wallet)["reported"], -25)
        self.assertEqual(team.details(self.wallet)["posted"], 100)
        frappe.set_user("Administrator")
        team.review(name, "Approve", "Checked receipt")
        values = team.details(self.wallet)
        self.assertEqual((values["reported"], values["posted"], values["pending"]), (-25, -25, 0))
        self.assertEqual(overview(self.project.name)["spent"], 125)
        self.fund(50)
        self.fund(10, "Return")
        self.assertEqual(team.details(self.wallet)["posted"], 15)
        self.assertEqual(overview(self.project.name)["spent"], 125)
        team.reverse_transfer(funding, "Transfer entered twice")
        self.assertEqual(team.details(self.wallet)["posted"], -85)

    def test_permissions_native_api_and_assignment_revocation(self):
        frappe.set_user(self.user)
        name = self.submit()
        self.assertEqual([w["name"] for w in team.bootstrap()["wallets"]], [self.wallet])
        self.assertEqual(len(frappe.get_list("Construction Site Entry", pluck="name")), 1)
        doc = frappe.get_doc("Construction Site Entry", name)
        self.assertTrue(doc.has_permission("read"))
        self.assertFalse(doc.has_permission("write"))
        doc.amount = 1
        with self.assertRaises(frappe.PermissionError):
            doc.save()
        with self.assertRaises(frappe.PermissionError):
            doc.save(ignore_permissions=True)
        with self.assertRaises(frappe.PermissionError):
            frappe.delete_doc("Construction Site Entry", name, ignore_permissions=True)
        for action in (lambda: team.review(name, "Approve", "Forged"), lambda: self.fund(),
                       lambda: team.grant_correction(name), lambda: team.assign(self.project.name, self.user),
                       lambda: overview(self.project.name), lambda: frappe.get_list("Salary Slip"),
                       lambda: frappe.get_list("GL Entry"), lambda: team.create_user("bad@example.test", "Bad", "bad")):
            with self.assertRaises(frappe.PermissionError):
                action()
        frappe.set_user("Administrator")
        team.set_enabled(self.wallet, 0)
        frappe.set_user(self.user)
        for action in (lambda: team.details(self.wallet), lambda: self.submit(), lambda: team.request_correction(name, "Fix")):
            with self.assertRaises(frappe.PermissionError):
                action()
        self.assertEqual(frappe.get_list("Construction Site Entry"), [])

    def test_other_supervisor_and_guest_cannot_read_or_modify(self):
        name = self.submit()
        other = frappe.get_doc({"doctype": "User", "email": f"other-{uuid4()}@example.test", "first_name": "Other",
            "send_welcome_email": 0, "user_type": "Website User", "roles": [{"role": "Construction Supervisor"}]}).insert().name
        for user in (other, "Guest"):
            frappe.set_user(user)
            for action in (lambda: team.details(self.wallet), lambda: self.submit(),
                           lambda: team.request_correction(name, "Fix")):
                with self.assertRaises(frappe.PermissionError):
                    action()
            self.assertFalse(frappe.get_doc("Construction Site Entry", name).has_permission("read"))
        frappe.set_user(other)
        self.assertEqual(frappe.get_list("Construction Site Entry"), [])

    def test_one_time_correction_preserves_history_and_replaces_accounting(self):
        self.fund()
        frappe.set_user(self.user)
        name = self.submit()
        with self.assertRaises(frappe.PermissionError):
            self.submit(payload=self.expense(amount=80), revision=name)
        team.request_correction(name, "The receipt was 80, not 125")
        frappe.set_user("Administrator")
        first = team.review(name, "Approve", "Receipt initially checked")["voucher"]
        with self.assertRaises(frappe.PermissionError):
            frappe.get_doc("Purchase Invoice", first).cancel()
        team.grant_correction(name)
        frappe.set_user(self.user)
        replacement = self.submit(payload=self.expense(amount=80), revision=name)
        with self.assertRaises(frappe.ValidationError):
            team.request_correction(replacement, "Cannot nest a pending correction")
        self.assertEqual(team.details(self.wallet)["reported"], -25)
        with self.assertRaises(frappe.PermissionError):
            self.submit(payload=self.expense(amount=70), revision=name)
        frappe.set_user("Administrator")
        team.review(replacement, "Approve", "Corrected receipt checked")
        self.assertEqual(frappe.db.get_value("Purchase Invoice", first, "docstatus"), 2)
        self.assertEqual(frappe.db.get_value("Construction Site Entry", name, "state"), "Superseded")
        self.assertEqual(frappe.db.get_value("Construction Site Entry", name, "amount"), 125)
        self.assertEqual(team.details(self.wallet)["posted"], 20)
        self.assertEqual(overview(self.project.name)["spent"], 80)
        team.review(replacement, "Approve", "Retry")
        self.assertEqual(overview(self.project.name)["spent"], 80)

    def test_attendance_approval_correction_and_duplicates(self):
        frappe.set_user(self.user)
        name = self.submit("Attendance", self.mark())
        with self.assertRaises(frappe.ValidationError):
            self.submit("Attendance", self.mark())
        frappe.set_user("Administrator")
        first = team.review(name, "Approve", "Hours checked")["voucher"]
        self.assertEqual(frappe.db.get_value("Attendance", first, "actual_overtime_duration"), 2)
        frappe.set_user(self.user)
        team.request_correction(name, "Only one hour overtime")
        frappe.set_user("Administrator")
        team.grant_correction(name)
        frappe.set_user(self.user)
        replacement = self.submit("Attendance", self.mark(ot=1), revision=name)
        frappe.set_user("Administrator")
        second = team.review(replacement, "Approve", "Correction checked")["voucher"]
        self.assertEqual(frappe.db.get_value("Attendance", first, "docstatus"), 2)
        self.assertEqual(frappe.db.get_value("Attendance", second, "actual_overtime_duration"), 1)
        self.assertEqual(team.details(self.wallet)["posted"], 0)

    def test_retries_validation_rejection_and_pending_correction(self):
        key = str(uuid4())
        funding = self.fund(key=key)
        self.assertEqual(self.fund(key=key), funding)
        with self.assertRaises(frappe.ValidationError):
            self.fund(amount=200, key=key)
        frappe.set_user(self.user)
        key = str(uuid4())
        name = self.submit(key=key)
        self.assertEqual(self.submit(key=key), name)
        with self.assertRaises(frappe.ValidationError):
            self.submit(payload=self.expense(amount=1), key=key)
        for value in (0, -1, "NaN", "1.001"):
            with self.assertRaises(frappe.ValidationError):
                self.submit(payload=self.expense(amount=value))
        team.request_correction(name, "Correct amount")
        frappe.set_user("Administrator")
        team.grant_correction(name)
        frappe.set_user(self.user)
        replacement = self.submit(payload=self.expense(amount=75), revision=name)
        self.assertEqual(team.details(self.wallet)["pending"], 125)
        frappe.set_user("Administrator")
        team.review(replacement, "Reject", "Receipt does not match")
        self.assertEqual(team.details(self.wallet)["pending"], 125)
        team.review(name, "Reject", "Not a business expense")
        self.assertEqual(team.details(self.wallet)["reported"], 100)

    def test_owner_login_and_restricted_supervisor_login_creation(self):
        owner = team.create_user(f"owner-{uuid4()}@example.test", "Owner", str(uuid4()), "Owner")["user"]
        frappe.set_user(owner)
        for doctype in ("Purchase Invoice", "Attendance", "Salary Slip", "Construction Cost Plan", "User"):
            self.assertTrue(frappe.has_permission(doctype, "create"), doctype)
        supervisor = team.create_user(f"new-super-{uuid4()}@example.test", "Supervisor", str(uuid4()))["user"]
        wallet = team.assign(self.project.name, supervisor)["wallet"]
        frappe.set_user(supervisor)
        self.assertEqual(team.bootstrap()["wallets"][0]["name"], wallet)
        self.assertFalse(frappe.has_permission("Purchase Invoice", "create"))

    def test_owner_can_void_and_revoke_but_supervisor_cannot(self):
        name = self.submit()
        team.review(name, "Approve", "Reviewed")
        frappe.set_user(self.user)
        team.request_correction(name, "Wrong amount")
        for action in (lambda: team.void_entry(name, "Unauthorized"), lambda: team.decline_correction(name, "Unauthorized")):
            with self.assertRaises(frappe.PermissionError):
                action()
        frappe.set_user("Administrator")
        team.grant_correction(name)
        team.decline_correction(name, "Receipt was correct")
        frappe.set_user(self.user)
        with self.assertRaises(frappe.PermissionError):
            self.submit(payload=self.expense(amount=50), revision=name)
        frappe.set_user("Administrator")
        team.void_entry(name, "Duplicate physical receipt")
        self.assertEqual(overview(self.project.name)["spent"], 0)
        self.assertEqual(team.details(self.wallet)["reported"], 0)
        self.assertEqual(frappe.db.get_value("Construction Site Entry", name, "state"), "Rejected")

    def test_cross_project_worker_and_fuel_validation(self):
        other = frappe.get_doc({"doctype": "Project", "project_name": "Other " + str(uuid4()),
            "company": self.company.name}).insert()
        worker = frappe.get_doc("Employee", self.worker)
        worker.custom_construction_project = other.name
        worker.save()
        frappe.set_user(self.user)
        with self.assertRaises(frappe.ValidationError):
            self.submit("Attendance", self.mark())
        with self.assertRaises(frappe.ValidationError):
            self.submit(payload=self.expense(vehicle="unrelated-vehicle", litres="10"))
        with self.assertRaises(frappe.ValidationError):
            self.submit(payload=self.expense(date=add_days(nowdate(), 1)))

    def test_owner_can_settle_after_revoking_access_and_closing_project(self):
        name = self.submit()
        team.review(name, "Approve", "Approved personal spending")
        team.set_enabled(self.wallet, 0)
        self.project.status = "Completed"
        self.project.save()
        self.fund(125)
        self.assertEqual(team.details(self.wallet)["posted"], 0)
        self.assertEqual(overview(self.project.name)["spent"], 125)

    def test_unassigned_sites_and_combined_supervisor_setup(self):
        project = frappe.get_doc({"doctype": "Project", "project_name": "Unassigned " + str(uuid4()),
            "company": self.company.name}).insert()
        self.assertIn(project.name, [p.name for p in team.bootstrap()["projects"]])
        email = f"combined-{uuid4()}@example.test"
        result = team.add_supervisor(project.name, email=email, full_name="New Supervisor", password=str(uuid4()))
        wallet = frappe.get_doc("Construction Site Wallet", result["wallet"])
        self.assertEqual((wallet.project, wallet.supervisor, wallet.enabled), (project.name, email, 1))
        self.assertFalse(frappe.has_permission("Purchase Invoice", "create", user=email))
        team.set_enabled(wallet.name, 0)
        self.assertEqual(team.add_supervisor(project.name, supervisor=email)["wallet"], wallet.name)
        self.assertEqual(frappe.db.get_value(wallet.doctype, wallet.name, "enabled"), 1)
        with self.assertRaises(frappe.ValidationError):
            team.add_supervisor(project.name, email=email, full_name="Duplicate", password=str(uuid4()))
        frappe.set_user(email)
        with self.assertRaises(frappe.PermissionError):
            team.add_supervisor(project.name, supervisor=self.user)
        self.assertNotIn("projects", team.bootstrap())

    def test_combined_setup_rejects_closed_site_before_creating_login(self):
        self.project.status = "Completed"
        self.project.save()
        email = f"closed-site-{uuid4()}@example.test"
        with self.assertRaises(frappe.ValidationError):
            team.add_supervisor(self.project.name, email=email, full_name="No access", password=str(uuid4()))
        self.assertFalse(frappe.db.exists("User", email))
