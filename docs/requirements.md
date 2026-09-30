# Construction ERP requirements — pilot baseline 0.5

**Status:** Updated with owner/supervisor access and site-money custody, 2026-09-30. Business rules and payroll compliance still need validation before live use.

## Purpose and scope

Use ERPNext as the core system to manage multiple concurrent construction projects, with Frappe HR for people and fleet features where appropriate. The first outcomes are reliable project costs, tender-estimate comparisons, payroll and advances, attendance and site time, materials/tools/subcontractors, fuel tracking, and a usable project schedule. Any custom app or report should extend the standard records rather than create a second accounting source of truth.

The expected initial scale is 1–2 active projects, 10–20 workers, 4–6 vehicles, 3–4 machines, and one user (the business owner), with a possible supervisor later. There is no historical data or suitable real project for the pilot. Use clearly labeled synthetic data. LKR is the expected main currency; other-currency needs and the legal payroll jurisdiction are unconfirmed.

## Core records and rules

- **Project:** A separate record for each construction job. Every relevant cost and work item should be traceable to a project; shared costs need an explicit allocation rule.
- **Estimate baseline:** A versioned tender estimate, with line items containing a cost category/code, description, quantity, unit, rate, and estimated amount. Keep the submitted tender baseline visible after revisions.
- **Cost category:** A reusable global category list is available when starting a project. Each project can add categories specific to its tender. These may map to a global reporting group so company-wide comparisons remain meaningful. Categories must be usable across estimate, purchasing, labour, fuel, and reporting. The proposed starting list is below.
- **Actual cost:** A posted expense or accounting entry. A purchase commitment, wage advance payout, and later salary payment must not also be counted as a second actual cost.
- **Wage advance:** Money paid to an employee before wages are due. Record the payout and remaining balance. For each advance, the user chooses whether to deduct it from the next pay or repay it over several pay periods, without reducing the labour cost attributed to a project.
- **Work item:** A project task with quantity/unit, planned dates, dependencies, crew requirement, progress, and optionally a productivity rate. Actual hours and quantities should be recordable separately from the plan.

## Requirements

| ID | Need | Initial acceptance check |
| --- | --- | --- |
| R1 | Record all project expenses with date, amount, category, project, payee/source, and supporting document where available. | A manager can open a project and trace a reported total back to its source transactions. |
| R2 | Define reusable global cost categories and project-specific categories, then compare each project's actual and committed costs with the tender estimate by category and in total. Show remaining budget, variance, and an over-budget indicator. | A new project can use the global category list without re-entry and add its own categories. A category view shows baseline, approved revisions, current budget, open commitments, actual, forecast final cost, and variance; project-specific categories can roll up in company-wide reports. |
| R3 | See project dashboards over time and a projected final cost. | The dashboard shows trend and forecast assumptions, distinguishes measured costs from estimates, and uses the pilot forecast formula below. |
| R4 | Run employee payroll on a daily, weekly, or monthly schedule chosen for each worker. Calculate pay using either a fixed amount per pay period or the worker's days/hours worked and rate. Track wage advances, repayments, and outstanding balances; choose full deduction from the next pay or instalments across several pay periods for each advance. Attribute labour cost to the worker's project. | Payroll runs on the chosen schedule and pay method; a salary slip shows the agreed advance deduction; an employee's remaining advance balance reconciles to payouts and deductions; project labour totals do not double count them. |
| R5 | Record fuel for vehicles and machinery, including quantity, cost, date, equipment, and project/usage allocation. | A manager can compare fuel use and cost by equipment, project, and period. Efficiency uses distance or engine hours only when readings are available. |
| R6 | View a project Gantt chart with planned start/end dates, dependencies, and progress; add custom work items. | A user can add and edit an item and see the schedule change. |
| R7 | Recalculate planned task durations and dates when available workers, working hours, dependencies, or quantities change. | Changing a task's crew, quantity, productivity assumption, or deadline updates its feasible dates or required crew. The system shows which assumption caused the change. |
| R8 | Let a user describe a work item in natural language and turn it into structured fields. | The user sees the extracted quantity, unit, crew size, productivity, and assumptions, can edit them, and confirms before a task is saved. Missing or ambiguous values are flagged. |
| R9 | Record daily attendance and, when pay or costing needs it, hours worked against a project. | The owner can enter present/absent/half-day status and hours for a worker, review the pay period, and trace variable wages to approved records. |
| R10 | Track materials, tools, and subcontractors against projects. | The owner can see material receipts/issues and stock on hand, tool assignment/return, and subcontractor commitments and costs for a project. |
| R11 | Separate owner and supervisor logins. The owner has administration and business access; supervisors can submit attendance, OT and daily expenses only for assigned projects. | Supervisors cannot access payroll or company accounts, approve costs, or edit/delete submitted records through either the screen or API. Corrections require an owner grant for that specific record, preserve the original and require approval before replacing it. Revoking an assignment removes supervisor access immediately. |
| R12 | Include Meals in project budgets and expense categories. Track spending per meal and per person, compare with an expected cost per person, and notify the owner when it is exceeded. Suggest each day's headcount from project attendance and allow a manual adjustment for people who did not eat. | Meal expenses contribute once to project costs and the Meals category. A meal view shows attendance headcount, adjusted diners, total cost, actual cost per diner and expected cost. Multiple bills for the same meal are combined without counting diners twice. Over-limit meals are clearly flagged; missing attendance or a zero headcount never produces a misleading per-person figure. |

## Pilot defaults and calculations

**R13 — Expense history:** List all posted costs for the selected project, with a cumulative sum and a filtered total. Support category, date range, transaction source, description/supplier/reference search and minimum/maximum amount. Acceptance: totals reconcile with accessible expense ledger postings; credits reduce spending; running totals restart with filters and continue across pages. Drafts remain outside posted totals.

**R14 — Supervisor site money:** Track money given to each supervisor for each project, money returned, spending and reimbursement. Spending may exceed funds; a negative balance represents money owed back to the supervisor. Keep pending reported spending distinct from approved accounting costs. Funding and reimbursement are transfers, not extra expenses. Acceptance: giving 100 and spending 125 shows -25; approving the expense leaves that balance unchanged; reimbursing 25 clears it without another project expense. Transfers and corrections must preserve an audit trail. This is site cash custody, separate from wage advances.

- **Starting cost categories:** Materials, Labour, Subcontractors, Machinery and equipment, Fuel, Meals, Transport, Site overhead, Permits and fees, and Other. These are editable global defaults. A project may add categories of its own. Contingency is a budget reserve, not an actual expense category.
- **Budget versions:** Preserve the submitted tender as the original baseline. Show an approved revised budget separately and use it as the current budget if one exists. The owner approves revisions; the pilot does not silently rewrite the tender.
- **Cost view:** Count an open purchase order's uninvoiced balance as a commitment. Count posted costs as actuals. Show available budget as current budget minus actuals minus open commitments. Show forecast final cost as actuals plus open commitments plus the owner's estimate of further uncommitted costs; show variance as current budget minus forecast. Warn on projected overruns, leaving a hard stop as a later decision.
- **Shared costs:** Record them separately until the owner allocates them to a project; do not distribute them automatically. Capture ordinary cost sources, including supplier purchases, petty cash, wages, fuel, and subcontractors.
- **Operations:** The owner can enter and approve records. Assigned supervisors submit locked expenses and attendance for owner review; changes require specific permission. Allow a per-project work calendar with up to seven working days per week. Schedule each project using its own crew; cross-project worker sharing is outside this pilot.
- **Resources:** Track odometer readings for vehicles. Record engine hours for machinery when the meter is available, and only then calculate litres per engine hour. Track materials as stock movements, tools as assigned/returned assets, and subcontractors as project-linked commitments and costs. Exact workflows will be tested in ERPNext.
- **Meals:** Meals belong in the tender/current budget and actual expense reports. Record a meal against a project, date and meal type; combine its bills before calculating cost per head. Attendance provides a suggested headcount, not proof that everyone ate. Keep the attendance suggestion and manual adjustment visible, with a reason for adjustment. Preserve the expected-rate snapshot for historical comparisons. Provisional next-milestone defaults: separate breakfast/lunch/dinner limits per project and in-app alerts, subject to owner review.

### Example work-item entry

For example: “Tile 1,000 sq ft of floor. A crew of 10 workers can lay about 100 sq ft in one 8-hour shift.” The system should propose a task with area, unit, crew size, and crew productivity, then let the user correct those values. This sentence illustrates the input style; its quantities and rate are not business defaults. The original example meant that the **10-person crew together** completes the stated area. We must agree how productivity changes with a different crew size rather than assume it scales linearly.

The schedule calculation should use structured inputs and a deterministic formula. An LLM may help parse free text, but its output must be reviewed and must not silently decide dates, rates, or budget values.

## ERPNext starting point

| Need | Likely starting point | Fit to verify in a prototype |
| --- | --- | --- |
| Projects, tasks, and Gantt | ERPNext Project and Task; task Gantt uses planned dates and dependencies. | Task layout, progress, and whether it meets the manager's daily view. |
| Project expenses and budgets | ERPNext project-linked transactions and project budgets; Budget Variance Report. | Reusable global categories, project-specific additions and rollups, mapping from tender items to ledger costs, commitment logic, and dashboard layout. |
| Payroll, attendance, and wage advances | Frappe HR payroll, Attendance, and timesheets. Its Salary Structure includes daily, weekly, and monthly payroll frequencies, fixed salary components, and timesheet-based pay. A salary deduction can be represented with a payroll component/Additional Salary, but the wage-advance payout and balance workflow need a prototype. | Per-worker pay frequency and pay method, day/hour recording, payout and deduction reconciliation, and instalment handling. Frappe HR's standard Employee Advance is documented for employee expenses settled by Expense Claim, so it is not assumed to be the wage-advance solution. |
| Fuel and fleet | Frappe HR Vehicle and Vehicle Log, including odometer/fuel entries and vehicle expense reports. | Machinery with engine-hour meters and project-specific fuel allocation. |
| Capacity scheduling and free-text entry | Custom extension likely required. | Agreed productivity model, worker availability, calendar, and input review flow. |
| Materials, tools, and subcontractors | ERPNext Items, Stock Entry, purchasing, and project-linked transactions. | Project material issues and valuation, tool check-out/return, subcontractor scope and commitments. |

This is a capability map, not a final implementation choice. We will test standard configuration with sample business data before specifying custom fields, reports, or an app.

## Details to validate during the pilot

1. Confirm the company's country, statutory payroll deductions, and whether any transactions use a currency other than LKR before processing live payroll or accounts.
2. Test daily, weekly, and monthly fixed/attendance-based pay and wage-advance instalments in the chosen Frappe HR version.
3. Confirm actual tender categories, units, revision approvals, and the treatment of shared costs when a real project becomes available.
4. Confirm how the owner wants to enter daily attendance and hours, and whether a worker's pay method can change over time.
5. Validate machinery engine-hour availability, project fuel allocation, material valuation, and tool tracking with sample equipment/items.
6. Agree the scheduling mode (finish date for a fixed crew, crew needed for a deadline, or both), site hours, and how productivity changes with crew size.
7. Decide later whether the optional supervisor needs phone/offline entry and how the pilot will be hosted. No historical import is planned.

## Milestones

1. **Requirements baseline — complete:** Capture the agreed scope and provisional defaults, with synthetic pilot data where real examples are unavailable.
2. **ERPNext pilot and application foundation — complete:** Install the custom Frappe app alongside ERPNext/HRMS, preserve development data, provide simple lifecycle commands, and validate a synthetic project with expenses, budgets, tasks, payroll, stock and a vehicle log. The first category-management forms are also available; category/account mapping and cost dashboards remain subsequent work.
3. **Tender and cost plan — complete:** Submitted tender protection, controlled revisions, account/category validation and cancellation recovery.
4. **Current project cost view — complete:** Category chart and report comparing submitted tender/current budget with actual expense postings and uninvoiced orders. Unmapped costs remain visible; possible receipt/accrual overlaps require reconciliation. See [calculation boundaries](cost-reporting.md).
5. **Simplified daily work — complete:** Project overview and guided direct expense entry with private receipts, draft review and standard accounting postings. Attendance and fuel are extended in milestone 7. See the [daily work guide](daily-work.md).
6. **Forecasts and trends:** Add separately maintained estimates of further uncommitted work, historical comparisons and receipt reconciliation automation.
7. **Site attendance, categories and fuel — delivered for review:** Crew attendance/regular hours/OT, draft confirmation, category spending drilldown and equipment-linked fuel capture. Payroll/advance payments, fuel efficiency and trend reporting remain subsequent work.
8. **Planning:** Add capacity-aware scheduling and reviewed natural-language work-item entry.
9. **Meals budget and cost-per-head controls — delivered for review:** Meals category and budget integration; confirmed-attendance suggested diners, manually adjustable headcounts with reasons, expected costs per person, combined meal bills and in-app over-limit alerts. Historical attendance/rate snapshots and diner corrections are preserved. Current defaults use breakfast/lunch/dinner limits per project; the owner can review these defaults.
10. **Simplified payroll and wage advances:** Owner-facing daily/weekly/monthly pay runs, OT rate configuration, wage advances and next-pay/instalment deductions, using the standard HRMS payroll records.
11. **Expense history — delivered for review:** All expenses view with category/date/source/search/amount filters, document links, filtered totals and cumulative amounts across pages. Uses posted project expense accounts, including costs entered through other ERPNext workflows.
12. **Owner/supervisor access and site money — delivered for review:** Separate logins and project assignments, restricted supervisor attendance/OT and expense submissions, immediate locking, owner review, one-use correction grants, project/supervisor cash balances, funding/returns/reimbursements, negative balances and auditable native accounting vouchers. Initial default: attendance and expenses require owner approval; negative reported balances are allowed.
13. **Simpler supervisor setup — delivered for review:** Owners see all sites before any supervisor is assigned. A single Add supervisor flow creates a restricted login and grants site access, or reuses an existing supervisor and cash history. Empty states explain the next step; owner account creation is kept in a separate expandable section.

Each completed milestone gets a separate local, Git-ignored numbered devlog and a Git commit for the corresponding repository changes. Future milestone scope and order may change after the pilot.

## Product references

- [ERPNext Project](https://docs.frappe.io/erpnext/project), [Tasks](https://docs.frappe.io/erpnext/tasks), and [Project Views](https://docs.frappe.io/erpnext/project-views)
- [ERPNext Budget](https://docs.frappe.io/erpnext/budget) and [Project Profitability](https://docs.frappe.io/erpnext/project-profitability)
- [Frappe HR Salary Structure](https://docs.frappe.io/hr/salary-structure), [Attendance](https://docs.frappe.io/hr/attendance), [Additional Salary](https://docs.frappe.io/hr/additional-salary), and [Employee Advance](https://docs.frappe.io/hr/employee-advance)
- [Frappe HR Vehicle Log](https://docs.frappe.io/hr/vehicle-log) and [Fleet Management](https://docs.frappe.io/hr/fleet-management)
- [ERPNext Stock Entry](https://docs.frappe.io/erpnext/stock-entry)
