FROM frappe/erpnext:v16.36.0@sha256:295574c6a112d790a1a16f8c8c8ec3b987b6c8e235818bfd14f0fccaf1db7672 AS erpnext

FROM erpnext

# ERPNext includes Frappe. Bake HR into the same image used by every service.
RUN bench get-app --branch v16.20.0 https://github.com/frappe/hrms \
    && cp -a sites/assets/. /home/frappe/frappe-bench/assets/

# Fail a rebuild if the upstream release tag ever points to different source.
RUN test "$(git -C apps/hrms rev-parse HEAD)" = c0a04b80eeb721417b75cea758e831464d0da041

# Keep upstream bundle entries when adding the HRMS asset manifest.
COPY --from=erpnext /home/frappe/frappe-bench/assets/assets.json /tmp/upstream-assets.json
COPY --from=erpnext /home/frappe/frappe-bench/assets/assets-rtl.json /tmp/upstream-assets-rtl.json
RUN python -c 'import json; from pathlib import Path; [(lambda p, original: p.write_text(json.dumps({**json.loads(original.read_text()), **json.loads(p.read_text())})))(Path("assets") / name, Path("/tmp/upstream-" + name)) for name in ("assets.json", "assets-rtl.json")]'

COPY --chown=frappe:frappe pyproject.toml apps/hiru_construction/pyproject.toml
COPY --chown=frappe:frappe hiru_construction apps/hiru_construction/hiru_construction
RUN env/bin/pip install --no-cache-dir -e apps/hiru_construction
COPY --chown=frappe:frappe scripts/provision.sh /opt/hiru/scripts/provision.sh
