#!/usr/bin/env bash
set -euo pipefail
site=hiru-test.localhost
if [[ ! -f "sites/$site/site_config.json" ]]; then
  bench new-site "$site" --mariadb-user-host-login-scope='%' \
    --db-root-username root --db-root-password "$DB_ROOT_PASSWORD" \
    --admin-password "$PILOT_ADMIN_PASSWORD" --install-app erpnext
  bench --site "$site" set-config hiru_test 1
fi
env/bin/python - <<'PY'
import json
from pathlib import Path
if not json.loads(Path('sites/hiru-test.localhost/site_config.json').read_text()).get('hiru_test'):
    raise SystemExit('Refusing to run tests on an unmarked site')
PY
for app in hrms hiru_construction; do
  if ! bench --site "$site" list-apps | awk '{print $1}' | grep -qx "$app"; then
    bench --site "$site" install-app "$app"
  fi
done
bench --site "$site" set-config mute_emails 1
bench --site "$site" disable-scheduler
bench --site "$site" migrate
bench --site "$site" execute hiru_construction.tests.setup.prepare
if [[ "${1:-}" == browser ]]; then
  bench --site "$site" execute hiru_construction.tests.daily_browser.prepare
  exit 0
fi
bench --site "$site" set-config allow_tests true
trap 'bench --site "$site" set-config allow_tests false' EXIT
bench --site "$site" run-tests --app hiru_construction
