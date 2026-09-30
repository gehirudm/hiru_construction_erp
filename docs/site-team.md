# Site team and money

Open [Site team & money](http://localhost:8080/site-work) from the daily screen. The existing Administrator remains the initial owner until you create your father's separate login.

## Set up people

In **People & access**, create an Owner login for your father and a Supervisor login for each supervisor. Owner accounts receive administration, accounts, purchasing, stock, project, HR and payroll roles. Supervisors use a restricted website account; they do not receive standard accounting, HR or project-manager roles. Set an initial password of at least 12 characters and share it privately. This action sends no email.

Assign each supervisor to the projects they can work on. Every project/supervisor pair has a separate cash account and balance. Existing assignments are reused. Disable an assignment to revoke access to that project's screen, history and APIs; the owner retains the audit history. To disable the entire login or reset its password, use the owner's standard User administration screen. Do not grant supervisors additional ERPNext roles: those roles can independently grant broader access.

Workers must already be assigned to a project in the daily Attendance & OT screen. Suppliers and equipment must already exist. Supervisors receive only worker names, basic supplier/equipment choices and approved-budget category names, not company budgets, wages or ledger access.

## Money given and spent

The owner chooses the project/supervisor and uses **Give / return money** to record an actual handover, reimbursement or return, selecting the business cash/bank account and entering a note. This records accounting entries; it does not transfer money electronically.

The supervisor uses **Add expense** for money actually spent, including personal money spent after site funds run out. The form supports categories, supplier, date, amount, description and receipt number. Fuel requires equipment and litres, plus vehicle odometer readings. Meals link to a meal for the same project/date; the owner currently prepares the meal and diner count in the Meals screen. Receipt-image upload is currently available in the owner's original expense screen, not the supervisor form.

For example, give LKR 10,000 and submit LKR 12,000 of spending:

| Balance | Before expense approval | After approval |
| --- | ---: | ---: |
| Approved cash balance | 10,000 | -2,000 |
| Spending awaiting approval | 12,000 | 0 |
| Balance after reported spending | -2,000 | -2,000 |

The negative balance indicates reimbursement due to the supervisor. Record another 2,000 given to clear it. Funding and reimbursement do not add project expenses. If an expense is rejected, it stops reducing the reported balance. Owners can settle outstanding money after a project closes or a supervisor assignment is disabled, without restoring supervisor access. These totals reflect all recorded dates, not a bank balance or date-filtered cash statement.

## Attendance, review and corrections

Supervisors select workers, mark status and regular/OT hours, then submit the selected crew. A batch is atomic: either all its new marks save or none do. Saved records are locked immediately. The owner approves attendance before it becomes confirmed HRMS Attendance; this also makes it available to attendance-based meal headcounts. Hours captured here do not automatically configure or calculate OT pay.

In **History & review**, the owner inspects the details and approves or rejects each expense or attendance submission, with a note. Expense approval creates a paid Purchase Invoice against the supervisor's cash account. Approved costs appear once in the project's existing expense list and category reports. Owner review still applies normal period, company, equipment, accounting and HRMS validation.

To fix a saved record:

1. Select **Request correction** and explain the mistake.
2. The owner selects **Allow one correction** for that specific entry.
3. The supervisor selects **Enter correction** and submits a replacement. The original remains unchanged and continues to determine balances until approval.
4. The owner reviews the replacement. Approval cancels/replaces the earlier native invoice or attendance record and marks the old submission Superseded. Rejection leaves the original effective and requires a new correction request.

The permission is consumed when a replacement is submitted. It does not grant general editing or deletion rights. A pending correction must be reviewed before it can itself be corrected. The owner can decline a request or revoke an unused grant with a reason. Attendance corrections retain the employee and date. Standard cancellation restrictions still apply if downstream payroll or other documents prevent a reversal. Linked accounting/attendance records cannot be changed or canceled through the advanced forms to bypass this audit workflow. The owner can void an approved expense/attendance entry with a reason, or reverse an erroneous money transfer from its history card and record a corrected transfer. Pending corrections must be rejected before voiding their original.

## Checks and current boundaries

`make test` checks permissions, custody accounting, negative balances, retries, approvals and corrections on the isolated test site. `make test-team` checks separate logins, the owner setup forms and supervisor workflows in a browser; its synthetic records stay on that test site. `make stop` also stops the test frontend.

History is currently loaded in full for the small initial business. Large histories will need server-side pagination. Supervisor submissions do not yet upload receipt images, create suppliers, handle tax breakdowns or prepare meals. Those actions remain owner workflows. Live use still needs business acceptance, secure hosting and backup/restore validation.
