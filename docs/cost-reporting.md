# Project cost control

Open **Hiru Construction → Construction Cost Plan** and create a tender baseline for a project with a company assigned. Map each expense ledger to one category and enter the tender estimate and optional contingency reserve. Multiple accounts may belong to a category; an account cannot appear twice in one plan. Accounts must be enabled expense ledgers belonging to the project's company. Categories can be global or belong to this project.

Save drafts freely. Submit the tender to approve it. Only one submitted tender is allowed per project, and submitted values are protected by Frappe's document lifecycle. System Managers and Projects Managers approve plans. These existing ERP roles are the initial permission policy; supervisor-specific entry/approval roles remain future work.

Use **Create Revision** on an approved plan. The form copies original tender values and starts the revised amounts from the current budget. Enter a new plan name and change **Approved Revision** amounts. Original accounts, categories and tender estimates must remain intact; set a revised amount to zero to remove a line's budget. New accounts have zero original tender estimate. Submit to activate the revision. Older revisions remain available as Superseded. Cancelling the current revision restores the latest remaining submitted revision, or the tender if none remain. A tender cannot be cancelled while submitted revisions reference it. Approval and cancellation lock the project so simultaneous actions are serialized.

Open **Construction Project Costs**, choose a project, and refresh after changing transactions. The report includes a category chart, summary cards and account-level rows:

| Value | Calculation |
| --- | --- |
| Original tender | Submitted baseline estimates |
| Current budget | Latest active submitted revision; otherwise the baseline. Zero is a valid revised amount. |
| Contingency reserve | Current plan's reserve, shown separately and not automatically added to spendable budget |
| Actual | Company-currency debits minus credits on project-tagged expense GL entries; cancelled entries and year-end Period Closing Vouchers excluded |
| Open orders | Submitted, non-closed/non-cancelled PO lines allocated to the project, net of invoiced amounts |
| Known exposure | Actual plus open orders, where receipt reconciliation is not outstanding |
| Budget remaining | Current budget minus known exposure; negative values highlighted |

The report is a current whole-project view, not a historical date snapshot. All posting dates are included, including future-dated submitted entries. Purchase commitments use the PO line's net company-currency amount multiplied by its uninvoiced proportion (`1 - billed_amt / amount`, floored at zero). This respects the order exchange rate and header discounts. Orders on hold remain commitments until closed or cancelled. PO taxes and charges are excluded from commitments; actual expensed taxes remain in GL costs. This report does not estimate final cash requirements or future uncommitted work.

Received-but-uninvoiced order lines can overlap recognized costs through accruals or stock consumption. Affected rows show **Review unbilled receipts**; combined exposure and remaining budget are withheld for those rows and the project remaining-budget summary until reconciled. The report still shows the separate actual and order amounts. Do not treat their sum as a reconciled forecast.

Unmapped expense accounts and order lines remain visible with **Needs mapping**, rather than disappearing from totals. Assign accounts through a revision. Costs without a project allocation are outside this project's report and must be allocated in the source transaction. Salary expense comes from payroll accruals, not a second sum of payslips/payments; wage advances and balance-sheet movements are excluded. Fuel claims likewise contribute via their expense postings only.

The report is restricted to System Managers and Projects Managers, checks project and plan read access, and exposes category-level cost aggregates rather than employee payroll details. Projects Users do not receive report access merely from their read access to plans.

## Local verification

Start with `make start`. `make seed` installs the optional demo tender and transactions; `make verify` checks the ledger and report totals. The original tender is LKR 375,000. A Meals revision adds LKR 30,000, so the current sample budget is LKR 405,000, actuals LKR 132,000, open orders LKR 60,000 and remaining budget LKR 213,000.

`make test` creates/reuses **hiru-test.localhost**, marked exclusively for tests, on the local database service. It installs the same apps and uses its own company and fixtures. Tests refuse to run on the demo site. The test site's email and scheduler are disabled. Its database persists in the existing development volumes and is separate from **hiru.localhost**. Run `npm run test:browser` against the seeded demo to verify navigation, chart rendering, report totals and revision creation; that check opens an unsaved revision and does not submit one.

Forecast estimates, historical trends, receipt reconciliation automation, and detailed resource planning are subsequent work.
