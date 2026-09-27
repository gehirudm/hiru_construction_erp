# Construction ERP

An installable Frappe app extending ERPNext and Frappe HR for construction project management.

The [requirements baseline](docs/requirements.md) captures scope and decisions. See [development instructions](docs/pilot.md) and [architecture](docs/architecture.md). Private milestone devlogs live in Git-ignored `devlogs/`.

```sh
make start   # start the development VM, containers, and migrate the app
make stop    # stop this project's containers; preserve all data
make sleep   # also stop the dedicated Colima VM to free memory
```

Open http://localhost:8080. Login: `Administrator`; password: `PILOT_ADMIN_PASSWORD` in local `.env`. Demo data is optional: `make seed`, then `make verify`.

Use **Hiru Construction → Construction Project Costs** for the category chart and tender/budget/expense/order comparison. [Cost reporting guide](docs/cost-reporting.md) explains approval, revisions, and calculation boundaries. `make test` runs automated checks on a separate test site; it never runs them against the demo company.

This is a development environment. Live deployment, backups, supervisor permissions, and statutory payroll configuration remain future work.

## Working agreement

- Review and revise the pilot baseline as real project workflows become available.
- At each completed milestone, commit the relevant repository changes and add a new local, numbered devlog describing what was delivered, how it was built, the work performed, validation, and the milestone achieved.
- Keep proposed future milestones in the requirements draft until their scope is agreed.
