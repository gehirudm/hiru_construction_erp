import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class ConstructionMeal(Document):
    def validate(self):
        from hiru_construction.daily import checked_project
        from hiru_construction.meals import attendance_count, positive_amount, diner_count
        project = checked_project(self.project)
        if not self.meal_date or getdate(self.meal_date) > getdate():
            frappe.throw(_("Choose today or an earlier meal date."))
        if self.meal_type not in ("Breakfast", "Lunch", "Dinner"):
            frappe.throw(_("Choose breakfast, lunch or dinner."))
        self.currency = frappe.get_cached_value("Company", project.company, "default_currency")
        self.meal_key = hashlib.sha256(f"{self.project}|{getdate(self.meal_date)}|{self.meal_type}".encode()).hexdigest()
        self.meal_label = f"{self.meal_type} · {self.meal_date}"
        self.diners = diner_count(self.diners)
        self.expected_per_head = positive_amount(self.expected_per_head)
        old = self.get_doc_before_save()
        if old:
            if any(self.get(k) != old.get(k) for k in ("project", "meal_date", "meal_type", "attendance_headcount", "expected_per_head")):
                frappe.throw(_("A saved meal keeps its date, project, attendance snapshot and expected rate. Change defaults for future meals instead."))
        else:
            self.attendance_headcount = attendance_count(self.project, self.meal_date)
        if self.diners != self.attendance_headcount and not (self.adjustment_reason or "").strip():
            frappe.throw(_("Explain the headcount adjustment, for example two workers did not eat."))
        if old and self.diners != old.diners and not (self.adjustment_reason or "").strip():
            frappe.throw(_("Enter a reason for changing the diner count."))

    def on_update(self):
        from hiru_construction.meals import update_alert
        update_alert(self.name)
