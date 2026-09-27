# Application architecture

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

The category master ships with nine global defaults. Project-specific categories refer to a standard ERPNext Project. Duplicate names are rejected within a scope after whitespace and case normalization; a database unique key also protects concurrent writes. Categories used in submitted plans cannot change scope. Cost plans map accounts to categories for reporting without changing ERPNext GL postings. The standard Script Report reads the submitted plan, ledger and purchase orders; no parallel financial ledger is maintained.

`make test` runs integration tests on a separate marked test site, with explicit fixtures and without ERPNext's general Project test dependencies. Application tests refuse to run on the demo site. Upstream suites can commit unrelated fixtures and must also stay isolated. Browser checks (`npm ci`, then `npm run test:browser`) use the seeded sample site and require Chrome or an installed Playwright Chromium browser.
