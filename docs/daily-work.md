# Daily work

Open `/construction` after signing in. The Hiru Construction app icon opens this screen. The initial demo administrator lands here after login; existing user workspace preferences are preserved.

Choose a project to see its approved budget, posted expenses, open purchase orders and remaining budget, with category comparisons and a task list. Remaining budget is not a completion forecast. Receipt/order reconciliation warnings follow the detailed cost report. Projects need a submitted tender budget before quick expense entry is available.

## Record an expense

1. Select **Record expense**, choose a budget category, and describe the cost.
2. Select or add the supplier, enter the total and date, and indicate whether it has already been paid from business cash or bank.
3. Optionally add a receipt number and private image/PDF attachment.
4. Select **Save draft & review**. Check the details, then keep the draft or **Confirm & record expense**.

Drafts do not affect project costs. Posting creates normal ERPNext purchase invoice ledger entries. Already-paid expenses also record the cash/bank payment; this does not transfer money. Entered cents are preserved without whole-currency rounding. Repeated save/post requests do not duplicate an expense. A changed draft must be reviewed again. Reopen drafts and recorded entries from the most recent 20 daily expenses.

Use advanced entry for inventory, purchase orders, payroll, tax breakdowns, corrections/cancellations and payment of previously unpaid invoices. Quick entry does not calculate tax from a total or replace these workflows. Budget categories map to expense accounts during setup; users do not need to select ledger accounts for ordinary expense entry.

## Access and validation

Daily work requires System Manager or Projects Manager access and retains standard document permissions. Projects Manager alone does not grant accounting authority. Supervisor roles still need configuration before live use. Receipts use Frappe's private file storage and document access checks.

Run `make test` for isolated integration tests. With Node dependencies installed (`npm ci`) and Chrome or Playwright Chromium available, `make test-ui` prepares the separate test site and checks login, mobile layout, private receipts, draft review and posting. Its localhost-only frontend uses port 8081. Browser checks cancel their posted test expense afterward; no demo financial records are changed. `make stop` and `make sleep` include this test frontend.
