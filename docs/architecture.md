# Application architecture

`Construction Site Wallet` defines a project/supervisor assignment and a dedicated company-currency Cash account. `Construction Site Entry` stores immutable reported attendance/expenses and money movements, review metadata, one-use correction permission and links to native vouchers. `site_team.py` provides explicitly scoped APIs; supervisors receive only the portal role, no accounting/HR/project roles. DocType query/document permissions constrain list and direct reads, including disabled assignments. Native create/write/delete routes cannot mutate these records; service-scoped context permits controlled updates with Frappe version tracking.

Owner bootstrap lists projects independently of wallet assignments. The site picker therefore includes unassigned projects, while supervisor bootstrap continues to expose only enabled assignments. The owner-only `add_supervisor` POST creates the restricted User and assignment in one request transaction, or reuses/enables an existing supervisor assignment without changing their password or cash history.

Wallet row locks serialize transfers, review and corrections; employee locks prevent duplicate marks across supervisors. UUID/hash requests make retries idempotent. Approval uses the existing Purchase Invoice/Attendance services as the authenticated owner. Money transfers use Journal Entry and never hit expense accounts. Posted balances come from GL; pending original expenses reduce a separately labelled reported balance. Corrections preserve old payloads, consume one owner grant and replace approved vouchers atomically. Native voucher cancellation/update hooks prevent bypassing this workflow. New pages are `www/site-work.html`, `www/site_work.py` and `public/js/site-team.js`. Role setup runs before migration and after installation.

`expenses.py` exposes a read-only project expense listing backed by permission-filtered GL Entry records. Expense accounts and current approved cost-plan mappings define costs and categories. Decimal aggregation groups document/category rows, then applies filters and computes cumulative sums before pagination, without silently truncating history. Purchase Invoice metadata also respects document permissions. `public/js/expenses.js` renders the daily All expenses tab. This in-memory aggregation fits the initial project scale; larger histories will require database aggregation and performance validation.

Meal controls use `Construction Meal` (unique project/date/type, headcount and rate snapshots) and the `Construction Meal Rate` Project child table. Purchase Invoices link to a meal; meal totals are read from posted invoices, not a second ledger. Hooks validate the linked project/date/category and recompute over-limit alert state after posting, cancellation or headcount changes. A dedicated Notification Type is excluded from email delivery. Standard document permissions, versioning and a database unique meal key remain in effect.

The daily interface uses Frappe website routes in `hiru_construction/www/`, versioned assets in `public/`, and permission-checked methods in `daily.py`. Guided expenses create standard Purchase Invoices; custom fields store a unique retry identifier, request hash and category. No separate expense ledger is introduced. The optional test frontend serves only the isolated test site for `make test-ui`.

`site_work.py` manages project crew assignment and draft/confirmed HRMS Attendance. Regular hours supplement native total working hours and actual overtime duration. Employee locks serialize daily marks and normal permissions apply. `fuel.py` validates equipment-linked fuel fields on Purchase Invoice; equipment locks and submit-time validation prevent stale readings from posting. Company Vehicle/Asset records supply equipment identity. Fuel does not create a second claim or vehicle-log accounting path. Versioned extensions are installed by `site_work_fields.py`; the cost-category DocType selects General or Fuel entry.

`hiru_construction` is a normal, installable Frappe application, alongside unmodified `frappe`, `erpnext`, and `hrms` apps. The repository is the app source root, not a bench directory or an ERPNext fork.

| Path | Responsibility |
| --- | --- |
| `pyproject.toml` | Python package and supported Frappe app versions |
| `hiru_construction/hooks.py` | App registration and lifecycle hooks |
| `hiru_construction/modules.txt` | Construction module |
| `hiru_construction/construction/doctype/` | Versioned document schemas and controllers |
| `hiru_construction/construction/workspace/` | Versioned Desk workspace |
| `hiru_construction/workspace_sidebar/`, `desktop_icon/` | Frappe v16 navigation definitions |
| `hiru_construction/patches.txt` | Ordered future data migrations |
| `hiru_construction/demo/` | Explicit, development-only sample data and checks |
| `Dockerfile`, `compose.yaml`, `scripts/` | Local infrastructure and commands |

ERPNext remains the accounting, purchasing, stock, and project system of record. HRMS remains the employee, attendance, and payroll system of record. Custom construction features use DocTypes, controllers, reports, hooks and migrations, rather than scripts that reconstruct application behaviour on every startup.

The image packages the custom app with pinned ERPNext/HRMS versions. Local Compose mounts its Python source for development. Schema changes are applied by `bench --site hiru.localhost migrate` during `make start`. Python changes require restarting application processes. On an existing compatible bench, install the repository using `bench get-app <repository-url>` followed by `bench --site <site> install-app hiru_construction` (ERPNext and HRMS required). No remote repository is configured yet.

Installation never creates a demonstration company or financial transactions. `make seed` is a separate explicit action, restricted to the marked development site. The Compose project name and existing named volumes are retained to preserve earlier development data.

This structure supports normal Frappe deployment; the local Compose configuration is not a production deployment. A live release still needs managed secrets, TLS, tested backup/restore, operational monitoring, access roles and business acceptance checks.

The category master ships with ten global defaults, including Meals. Project-specific categories refer to a standard ERPNext Project. Duplicate names are rejected within a scope after whitespace and case normalization; a database unique key also protects concurrent writes. Categories used in submitted plans cannot change scope. Cost plans map accounts to categories for reporting without changing ERPNext GL postings. The standard Script Report reads the submitted plan, ledger and purchase orders; no parallel financial ledger is maintained. Expense entry types are General, Fuel and Meals.

`make test` runs integration tests on a separate marked test site, with explicit fixtures and without ERPNext's general Project test dependencies. Application tests refuse to run on the demo site. Upstream suites can commit unrelated fixtures and must also stay isolated. Browser checks (`npm ci`, then `npm run test:browser`) use the seeded sample site and require Chrome or an installed Playwright Chromium browser.
