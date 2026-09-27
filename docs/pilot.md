# Local ERPNext pilot

This milestone runs ERPNext and Frappe HR with synthetic construction records. It tests the standard accounting, payroll, stock, and project features before custom development. It is a local development environment, with HTTP bound to `127.0.0.1` and outbound site email muted.

## Start and stop

Requirements: Docker Engine with Compose and Buildx, and Python 3 for local credential generation. On this Apple Silicon Mac, Docker runs in the dedicated Colima profile `hiru-erp` (4 CPUs, 8 GB RAM, 50 GB disk limit). Start that profile with:

```sh
make start
make seed
make verify
```

Run commands from this repository. The helper automatically uses the dedicated Colima profile when Colima is installed; otherwise it uses Docker's current context. Set `HIRU_DOCKER_CONTEXT` to override it explicitly. The first start builds the image and creates the site. Later starts preserve credentials and database volumes and migrate the installed custom app. Seeding uses stable document names to avoid duplicate submitted transactions.

Open [the local site](http://localhost:8080) and sign in as `Administrator`. The randomly generated password is `PILOT_ADMIN_PASSWORD` in the local `.env` file. That file is created with owner-only permissions and is excluded from Git. Use the **Hiru Construction** workspace to open projects, categories, costs, people, vehicles, and materials.

```sh
make status
make logs
make stop
make sleep
```

Stopping preserves data. `colima stop hiru-erp` also releases the VM's resources. Do not remove the Docker volumes when you want to preserve pilot edits. The seed refuses to run on an unmarked site or alongside other companies.

## Synthetic walkthrough

The company is **Hiru Construction Demo**, using LKR, Sri Lanka as the sample locale, and a calendar-year 2026 fiscal year. These are demo settings, not a determination of the business's statutory configuration.

| Record | What to inspect |
| --- | --- |
| `PILOT-PROJECT-001` | Community hall renovation, with three dependent tasks visible in Gantt view. |
| Four `PILOT-BUDGET-*` records | Project budgets for subcontractors, labour, fuel, and materials. |
| `PILOT-PO-001` | LKR 100,000 subcontract order, 40% invoiced, LKR 60,000 still committed. |
| `PILOT-PINV-001` | LKR 40,000 posted to the project's subcontract cost account. |
| `PILOT-EMP-001` through `003` | Three fictional workers with monthly, weekly, and daily fixed pay. |
| `PILOT-PAYROLL-FIXED-001` through `003` | Submitted payroll and accrual entries for LKR 60,000, 18,000, and 3,000. These accrue wages; they do not send payments. |
| `PILOT-ATT-*` and `PILOT-TIME-001` | Three attendance records and one eight-hour project timesheet. Timesheet cost is zero; the GL gets labour cost from payroll. |
| `PILOT-STOCK-RECEIPT` / `PILOT-STOCK-ISSUE` | Ten sample tile boxes received, four consumed at LKR 500 each, six remaining. The receipt is synthetic opening stock, not a supplier purchase. |
| `PILOT-FUEL-001` / `PILOT-FUEL-CLAIM-001` | A 300 km odometer interval, 30 litres refuelled, and one linked LKR 9,000 project expense. Refuelling alone does not establish measured consumption or efficiency. |

The verification script reads submitted documents, stock balances, and the General Ledger. Expected project actuals are LKR 132,000: subcontractors 40,000 + labour 81,000 + materials 2,000 + fuel 9,000. Open purchase commitments are separate at LKR 60,000. It also checks that the company ledger balances and that each payroll has exactly one submitted salary slip.

## Boundaries of this milestone

- The **Hiru Construction** workspace and **Construction Cost Category** form are installed from versioned app files. Nine default global categories can be reused; additional categories can be global or restricted to a project. System Managers and Projects Managers can maintain categories; Projects Users can read them. This is the first category-management slice, not the final owner/supervisor role model.
- **Construction Cost Plan** is now available for tender and approved-revision lines. Each plan belongs to a project and records original estimate, approved revision, contingency, category and optional expense account. A project has one tender baseline; approved revisions supersede older approved revisions. This plan is an input to future dashboards and does not yet recategorize transactions.
- Gantt tasks have dates and dependencies. Crew-based duration calculation and reviewed natural-language entry are not implemented yet.
- The payroll examples exercise fixed daily, weekly, and monthly pay. Attendance-based amounts, wage-advance instalments, and statutory payroll rules still need dedicated implementation and checks.
- Vehicle fuel claims and stock issues use standard records. Machinery engine hours, fuel efficiency dashboards, tools, and detailed subcontract tracking remain future work.
- The pilot uses Administrator. The owner/supervisor permission model is not yet configured, and no external user invitations are sent.

## Versions and references

- ERPNext `v16.36.0` via the official `frappe/erpnext` image; Frappe is included in that image.
- Frappe HR `v16.20.0`, installed into the same image for the web server, workers, and scheduler.
- MariaDB `11.8.3` and Redis `7.4.2`.
- Deployment structure follows [Frappe Docker](https://github.com/frappe/frappe_docker) and its [custom app build guidance](https://github.com/frappe/frappe_docker/blob/main/docs/02-setup/02-build-setup.md).
- Functional references: [Budget](https://docs.frappe.io/erpnext/budget), [Attendance](https://docs.frappe.io/hr/attendance), [Payroll Entry](https://docs.frappe.io/hr/payroll-entry), [Vehicle Log](https://docs.frappe.io/hr/vehicle-log), and [Stock Entry](https://docs.frappe.io/erpnext/stock-entry).
