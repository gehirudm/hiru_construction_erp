# Construction ERP requirements — draft 0.1

**Status:** Discussion draft, 2026-09-26. These are initial needs, not an approved specification.

## Purpose and scope

Use ERPNext as the core system to manage multiple concurrent construction projects, with Frappe HR for people and fleet features where appropriate. The first outcomes are reliable project costs, tender-estimate comparisons, payroll and advances, fuel tracking, and a usable project schedule. Any custom app or report should extend the standard records rather than create a second accounting source of truth.

## Core records and rules

- **Project:** A separate record for each construction job. Every relevant cost and work item should be traceable to a project; shared costs need an explicit allocation rule.
- **Estimate baseline:** A versioned tender estimate, with line items containing a cost category/code, description, quantity, unit, rate, and estimated amount. Keep the submitted tender baseline visible after revisions.
- **Cost category:** A consistent category across estimate, purchasing, labour, fuel, and reporting (for example, materials, labour, equipment, subcontractors). The actual category list is to be agreed.
- **Actual cost:** A posted expense or accounting entry. A purchase commitment, wage advance payout, and later salary payment must not also be counted as a second actual cost.
- **Wage advance:** Money paid to an employee before wages are due. Record the payout and remaining balance, then recover it through agreed payroll deductions without reducing the labour cost attributed to a project.
- **Work item:** A project task with quantity/unit, planned dates, dependencies, crew requirement, progress, and optionally a productivity rate. Actual hours and quantities should be recordable separately from the plan.

## Requirements

| ID | Need | Initial acceptance check |
| --- | --- | --- |
| R1 | Record all project expenses with date, amount, category, project, payee/source, and supporting document where available. | A manager can open a project and trace a reported total back to its source transactions. |
| R2 | Compare each project's actual and committed costs with the tender estimate by category and in total. Show remaining budget, variance, and an over-budget indicator. | A category view shows baseline, approved revisions, current budget, committed, actual, and variance using clearly defined formulas. |
| R3 | See project dashboards over time and a projected final cost. | The dashboard shows trend and forecast assumptions, and distinguishes measured costs from estimates. Forecast method remains to be agreed. |
| R4 | Run employee payroll and track wage advances, repayments, and outstanding balances. Attribute labour cost to projects, including people working on more than one project. | A salary slip shows the agreed advance deduction; an employee's remaining advance balance reconciles to payouts and deductions; project labour totals do not double count them. |
| R5 | Record fuel for vehicles and machinery, including quantity, cost, date, equipment, and project/usage allocation. | A manager can compare fuel use and cost by equipment, project, and period. Efficiency uses distance or engine hours only when readings are available. |
| R6 | View a project Gantt chart with planned start/end dates, dependencies, and progress; add custom work items. | A user can add and edit an item and see the schedule change. |
| R7 | Recalculate planned task durations and dates when available workers, working hours, dependencies, or quantities change. | Changing a task's crew, quantity, productivity assumption, or deadline updates its feasible dates or required crew. The system shows which assumption caused the change. |
| R8 | Let a user describe a work item in natural language and turn it into structured fields. | The user sees the extracted quantity, unit, crew size, productivity, and assumptions, can edit them, and confirms before a task is saved. Missing or ambiguous values are flagged. |

### Example work-item entry

For example: “Tile 1,000 sq ft of floor. A crew of 10 workers can lay about 100 sq ft in one 8-hour shift.” The system should propose a task with area, unit, crew size, and crew productivity, then let the user correct those values. This sentence illustrates the input style; its quantities and rate are not business defaults. The original example meant that the **10-person crew together** completes the stated area. We must agree how productivity changes with a different crew size rather than assume it scales linearly.

The schedule calculation should use structured inputs and a deterministic formula. An LLM may help parse free text, but its output must be reviewed and must not silently decide dates, rates, or budget values.

## ERPNext starting point

| Need | Likely starting point | Fit to verify in a prototype |
| --- | --- | --- |
| Projects, tasks, and Gantt | ERPNext Project and Task; task Gantt uses planned dates and dependencies. | Task layout, progress, and whether it meets the manager's daily view. |
| Project expenses and budgets | ERPNext project-linked transactions and project budgets; Budget Variance Report. | Category mapping from tender items to ledger costs, commitment logic, and dashboard layout. |
| Payroll and wage advances | Frappe HR payroll and timesheets. A salary deduction can be represented with a payroll component/Additional Salary, but the wage-advance payout and balance workflow need a prototype. | Wage rules, payout and deduction reconciliation, and labour allocation across sites. Frappe HR's standard Employee Advance is documented for employee expenses settled by Expense Claim, so it is not assumed to be the wage-advance solution. |
| Fuel and fleet | Frappe HR Vehicle and Vehicle Log, including odometer/fuel entries and vehicle expense reports. | Machinery with engine-hour meters and project-specific fuel allocation. |
| Capacity scheduling and free-text entry | Custom extension likely required. | Agreed productivity model, worker availability, calendar, and input review flow. |

This is a capability map, not a final implementation choice. We will test standard configuration with sample business data before specifying custom fields, reports, or an app.

## Decisions to make together

1. **Pilot project and records:** Which active or completed project can supply a tender estimate and a few real expenses for the first walkthrough? Can sensitive amounts be replaced with sample values?
2. **Cost model:** What are the actual tender categories and units? Should budgets compare against the original tender, an approved revised budget, or both? How should shared head-office costs be allocated?
3. **Payroll and wage advances:** Are workers salaried, daily-paid, hourly-paid, or mixed? Are advances recovered from the next pay or across several pay periods? How is attendance or site time captured today?
4. **Fleet:** Which assets are road vehicles versus machinery? Are odometer or engine-hour readings available, and can one asset serve multiple projects in a day?
5. **Scheduling:** What is a normal workday/week, and are crews shared across projects? Should the system recommend a feasible end date for a fixed crew, or recommend workers needed to meet a fixed deadline, or both? Does the crew's output change proportionally as workers are added?
6. **Users and access:** Who enters costs and daily progress, who approves them, and who may see payroll? Does field staff need a phone-friendly interface or offline entry?
7. **Deployment:** Is there an existing ERPNext/Frappe HR installation, and is there a preferred hosting approach? This can wait until the workflow is agreed.

## Proposed milestones

1. **Requirements baseline:** Review this draft with the business owner; approve terms, sample workflows, and the pilot project's data.
2. **ERPNext pilot:** Set up a development instance with a sample project, expense, budget, task, payroll case, and vehicle log; document what standard features cover.
3. **Project cost view:** Implement the agreed tender baseline, category mapping, and budget/actual/commitment dashboard.
4. **People and fleet:** Configure payroll/advances and fuel capture with project allocation and useful reports.
5. **Planning:** Add capacity-aware scheduling and reviewed natural-language work-item entry.

Each completed milestone gets a separate local, Git-ignored numbered devlog and a Git commit for the corresponding repository changes. Milestone scope and order may change after the requirements review.

## Product references

- [ERPNext Project](https://docs.frappe.io/erpnext/project), [Tasks](https://docs.frappe.io/erpnext/tasks), and [Project Views](https://docs.frappe.io/erpnext/project-views)
- [ERPNext Budget](https://docs.frappe.io/erpnext/budget) and [Project Profitability](https://docs.frappe.io/erpnext/project-profitability)
- [Frappe HR Payroll Setup](https://docs.frappe.io/hr/payroll-setup), [Additional Salary](https://docs.frappe.io/hr/additional-salary), and [Employee Advance](https://docs.frappe.io/hr/employee-advance)
- [Frappe HR Vehicle Log](https://docs.frappe.io/hr/vehicle-log) and [Fleet Management](https://docs.frappe.io/hr/fleet-management)
