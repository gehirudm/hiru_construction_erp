#!/usr/bin/env bash
set -euo pipefail
site=hiru.localhost
if [[ ! -f "sites/$site/site_config.json" ]]; then
  bench new-site "$site" --mariadb-user-host-login-scope='%' \
    --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" \
    --admin-password "$PILOT_ADMIN_PASSWORD" --install-app erpnext
  bench --site "$site" set-config hiru_pilot 1
else
  env/bin/python - <<'PY'
import json
from pathlib import Path
config = json.loads(Path('sites/hiru.localhost/site_config.json').read_text())
if not config.get('hiru_pilot'):
    raise SystemExit('Existing site is not marked as a Hiru pilot; refusing to modify it.')
PY
fi
if ! bench --site "$site" list-apps | awk '{print $1}' | grep -qx hrms; then
  bench --site "$site" install-app hrms
fi
bench use "$site"
if ! bench --site "$site" list-apps | awk '{print $1}' | grep -qx hiru_construction; then
  bench --site "$site" install-app hiru_construction
fi
bench --site "$site" migrate
bench --site "$site" set-config mute_emails 1
bench --site "$site" set-config disable_telemetry 1
bench --site "$site" disable-scheduler
