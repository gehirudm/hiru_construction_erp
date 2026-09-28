# Daily work

Open `/construction` after signing in. The Hiru Construction app icon opens this screen. The initial demo administrator lands here after login; existing user workspace preferences are preserved.

Choose a project to see its approved budget, posted expenses, open purchase orders and remaining budget, with category comparisons and a task list. Remaining budget is not a completion forecast. Receipt/order reconciliation warnings follow the detailed cost report. Projects need a submitted tender budget before quick expense entry is available.

## Record an expense

Use the daily tabs for **Overview**, **Attendance & OT**, **Expense categories**, **Fuel & equipment**, and **Meals**.

1. Select **Record expense**, choose a budget category, and describe the cost.
2. Select or add the supplier, enter the total and date, and indicate whether it has already been paid from business cash or bank.
3. Optionally add a receipt number and private image/PDF attachment.
4. Select **Save draft & review**. Check the details, then keep the draft or **Confirm & record expense**.

Drafts do not affect project costs. Posting creates normal ERPNext purchase invoice ledger entries. Already-paid expenses also record the cash/bank payment; this does not transfer money. Entered cents are preserved without whole-currency rounding. Repeated save/post requests do not duplicate an expense. A changed draft must be reviewed again. Reopen drafts and recorded entries from the most recent 20 daily expenses.

Use advanced entry for inventory, purchase orders, payroll, tax breakdowns, corrections/cancellations and payment of previously unpaid invoices. Quick entry does not calculate tax from a total or replace these workflows. Budget categories map to expense accounts during setup; users do not need to select ledger accounts for ordinary expense entry.

## Access and validation

### Attendance and OT

Assign existing active employees to a site with **Add workers to site**. Each worker has one current site; this does not model shared crews or dated assignment history. Select the day, check the full-day hours (initial suggestion: 8), and use **Mark all present** or mark workers individually. Half day suggests half the entered full-day hours; all regular and OT hours remain editable before confirmation. Absent workers must have zero hours, and combined hours cannot exceed 24.

Save drafts during the day, then review and confirm after OT is known. The sheet writes standard HRMS Attendance with project, regular hours, total working hours and actual overtime duration. Confirmed records are locked; corrections use HRMS cancellation/amendment. Existing leave or other attendance records are not overwritten. The seven-day summary includes confirmed records only.

An existing OT type can be selected; without one the hours are captured for later payroll setup. This screen does not calculate or pay wages. Native HRMS overtime collection selects Present records, so OT on a Half Day needs payroll review. Daily/weekly/monthly payroll, rates and wage advances still require their own workflow.

### Category spending

Category cards show approved budget, posted spending, open orders and remaining budget. Open a card for its original tender comparison and the latest 50 expense ledger entries; totals include all entries. Add a category-specific expense from the detail screen. Global/project-specific labels are preserved. Category creation and budget approval/revisions still use setup. Unmapped costs remain visible and require mapping; receipt reconciliation warnings retain the existing cost report rules.

### Fuel

Fuel categories have **Expense Entry Type = Fuel**. Selecting one, or pressing **Record fuel**, requires a company vehicle or machinery Asset, litres and total receipt amount. Vehicle odometer is required; machinery engine hours are optional when unavailable. The screen shows the calculated price per litre and includes equipment details in the review.

Fuel is stored on the same Purchase Invoice as the expense. There is no additional Vehicle Log or Expense Claim, avoiding a second payable or cost. Readings are checked against posted fuel invoices across projects and existing vehicle readings/log dates, including again when a draft is posted. Enter fuel chronologically; a reading cannot move backwards. Cancellations remove the invoice from fuel history and accounting totals without altering the standard Vehicle master.

The fuel tab shows the latest 20 fills recorded through this workflow. Earlier Vehicle Logs remain in the fleet workspace. Purchased litres are not actual fuel consumption; efficiency calculations need reliable tank/usage data and remain future work. Company-owned vehicles and machinery must first exist in setup.

### Meals

Meals is a reusable expense category with **Expense Entry Type = Meals**. Include it in the project's tender or approved budget revision. Open **Meals**, choose a date, and set expected costs per person for breakfast, lunch and dinner as needed. These rates use the project's company currency and apply to new meals only.

The suggested headcount counts distinct employees with confirmed Present or Half Day attendance on that project/date. Drafts, absences, leave and attendance on other projects are excluded. Each meal has its own actual diner count, so someone who skipped lunch need not be counted. A manual difference requires a reason. With no confirmed attendance, enter the actual count and explain it, or confirm attendance first. Meal records require at least one diner; a zero count cannot produce a per-head figure.

Save the meal headcount, then use **Add breakfast/lunch/dinner expense**. Several supplier bills can link to the same meal; their posted totals are combined and divided by its single headcount. Draft bills do not count. The review previews the cost per head after the current bill is posted. Meals post through the same Purchase Invoice expense path and are counted once in project costs.

An over-limit meal is highlighted on its card, in recent meals and in a project alert banner. A standard ERPNext in-app notification goes to the meal record's creator (initially the owner); this notification type never emails. The threshold is strictly greater than expected rate × actual diners. Cancellation or a headcount correction recalculates the warning. Prior notifications remain as history, while the banner reflects current over-limit meals.

Attendance suggestions and expected rates are historical snapshots. Later attendance/rate changes do not rewrite saved meals. Diner corrections require the current record version and an explanation, and are tracked in document versions. The view shows the latest 30 meals and up to 50 current alert references; each meal's totals include all its linked posted bills.

The demo adds a synthetic LKR 30,000 Meals budget through `PILOT-MEALS-BUDGET-001`, preserving the LKR 375,000 original tender and bringing its current budget to LKR 405,000. Example breakfast/lunch/dinner rates are LKR 200/350/300, not recommended business rates. Existing expenses remain unchanged. Set real rates before entering live costs.

### Permissions and tests

Daily work requires System Manager or Projects Manager access and retains standard document permissions. Projects Manager alone does not grant accounting authority. Supervisor roles still need configuration before live use. Receipts use Frappe's private file storage and document access checks.

Run `make test` for isolated integration tests. With Node dependencies installed (`npm ci`) and Chrome or Playwright Chromium available, `make test-ui` prepares the separate test site and checks login, mobile layout, private receipts, draft review and posting. Its localhost-only frontend uses port 8081. Browser checks cancel their posted test expense afterward; no demo financial records are changed. `make stop` and `make sleep` include this test frontend.
