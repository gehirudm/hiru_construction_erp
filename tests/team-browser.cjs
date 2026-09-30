const assert = require('node:assert/strict');
const fs = require('node:fs');
const { randomUUID } = require('node:crypto');
const { chromium } = require('playwright');

async function main() {
  const env = Object.fromEntries(fs.readFileSync('.env', 'utf8').split('\n').filter(l => l && !l.startsWith('#')).map(l => {
    const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1)];
  }));
  const fixture = JSON.parse(fs.readFileSync('.local/team-fixture.json', 'utf8'));
  const base = `http://localhost:${process.env.HIRU_TEST_PORT || env.HIRU_TEST_PORT || 8081}`;
  const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(chrome) ? chrome : undefined) });
  const errors = [];
  async function login(user, password) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage(); page.setDefaultTimeout(20000);
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base + '/login');
    await page.waitForFunction(() => typeof window.login?.call === 'function');
    await page.locator('#login_email').fill(user); await page.locator('#login_password').fill(password);
    await page.locator('.btn-login:not(.btn-login-with-email-link)').click();
    await page.waitForURL(url => !url.pathname.startsWith('/login'));
    await page.goto(base + '/site-work');
    await page.waitForFunction(() => /History & review|not assigned|Create a supervisor/.test(document.querySelector('#team-content').textContent));
    return page;
  }
  async function waitCall(page, method, action) {
    const response = page.waitForResponse(r => r.url().endsWith('site_team.' + method) && r.request().method() === 'POST');
    await action();
    const result = await response, body = await result.json();
    assert.equal(result.ok(), true, body.exception || 'Site API failed');
    await page.waitForFunction(() => !document.querySelector('#wallet').disabled);
    return body.message;
  }
  async function tab(page, name) { await page.getByRole('button', { name, exact: true }).click(); }
  async function actWithReason(page, card, name, explanation, method) {
    await card.getByRole('button', { name, exact: true }).click();
    await page.locator('#action-reason').fill(explanation);
    return waitCall(page, method, () => page.locator('#action-form').getByRole('button', { name: 'Confirm', exact: true }).click());
  }
  try {
    const owner = await login('Administrator', env.PILOT_ADMIN_PASSWORD);
    await tab(owner, 'People & access');
    const email = `team-ui-${randomUUID()}@example.test`, password = randomUUID();
    await owner.locator('[name=full_name]').fill('Site Supervisor UI');
    await owner.locator('[name=email]').fill(email); await owner.locator('[name=password]').fill(password);
    await waitCall(owner, 'create_user', () => owner.getByRole('button', { name: 'Create login', exact: true }).click());
    await owner.locator('[name=project]').selectOption(fixture.project);
    await owner.locator('[name=supervisor]').selectOption(email);
    const assigned = await waitCall(owner, 'assign', () => owner.getByRole('button', { name: 'Assign project', exact: true }).click());
    await owner.waitForFunction(wallet => document.querySelector('#wallet').value === wallet, assigned.wallet);
    await tab(owner, 'Give / return money');
    await owner.locator('[name=kind]').selectOption('Funding');
    await owner.locator('[name=amount]').fill('100'); await owner.locator('[name=account]').selectOption(fixture.cash);
    await owner.locator('[name=explanation]').fill('UI cash given');
    await waitCall(owner, 'transfer', () => owner.getByRole('button', { name: 'Record money transfer', exact: true }).click());
    const supervisor = await login(email, password);
    assert.equal(await supervisor.locator('[data-tab=access]').count(), 0);
    assert.equal(await supervisor.locator('#wallet option').count(), 2);
    await tab(supervisor, 'Add expense');
    await supervisor.locator('[name=category]').selectOption(fixture.category);
    await supervisor.locator('[name=supplier]').selectOption(fixture.supplier);
    await supervisor.locator('[name=amount]').fill('125'); await supervisor.locator('[name=description]').fill('UI site delivery');
    const entry = await waitCall(supervisor, 'submit_entry', () => supervisor.getByRole('button', { name: 'Submit expense', exact: true }).click());
    await supervisor.waitForFunction(() => document.querySelector('#balances').textContent.includes('25.00')).catch(async error => {
      console.error(await supervisor.locator('body').innerText()); throw error;
    });
    assert.match(await supervisor.locator('#balances article strong').first().textContent(), /-.*25\.00/);
    const row = () => supervisor.locator(`[data-entry="${entry.name}"]`);
    assert.equal(await row().getByRole('button', { name: 'Approve', exact: true }).count(), 0);
    const denied = await supervisor.evaluate(async name => {
      const token = document.querySelector('meta[name=csrf-token]').content;
      const response = await fetch('/api/resource/Construction%20Site%20Entry/' + encodeURIComponent(name), {
        method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Frappe-CSRF-Token': token }, body: JSON.stringify({ amount: 1 })
      }); return response.status;
    }, entry.name);
    assert.equal(denied, 403, 'Supervisor must not bypass locked submissions using REST');
    await owner.reload(); await owner.selectOption('#wallet', assigned.wallet);
    await owner.locator(`[data-entry="${entry.name}"]`).waitFor();
    await actWithReason(owner, owner.locator(`[data-entry="${entry.name}"]`), 'Approve', 'Receipt checked', 'review');
    await supervisor.reload(); await row().getByText(/Approved/).first().waitFor();
    await actWithReason(supervisor, row(), 'Request correction', 'Receipt amount was 80', 'request_correction');
    await owner.reload(); await owner.selectOption('#wallet', assigned.wallet);
    await waitCall(owner, 'grant_correction', () => owner.locator(`[data-entry="${entry.name}"]`).getByRole('button', { name: 'Allow one correction' }).click());
    await supervisor.reload(); await row().getByRole('button', { name: 'Enter correction' }).click();
    await supervisor.locator('[name=amount]').fill('80');
    const corrected = await waitCall(supervisor, 'submit_entry', () => supervisor.getByRole('button', { name: 'Submit correction', exact: true }).click());
    await owner.reload(); await owner.selectOption('#wallet', assigned.wallet);
    await owner.locator(`[data-entry="${corrected.name}"]`).waitFor();
    await actWithReason(owner, owner.locator(`[data-entry="${corrected.name}"]`), 'Approve', 'Correction checked', 'review');
    await owner.waitForFunction(() => document.querySelector('#balances article strong').textContent.includes('20.00'));
    await supervisor.reload(); await tab(supervisor, 'Mark attendance & OT');
    await supervisor.locator('.team-check input').check();
    await supervisor.locator('[name=ot]').fill('2');
    await waitCall(supervisor, 'submit_crew', () => supervisor.getByRole('button', { name: 'Submit selected attendance' }).click());
    await owner.reload(); await owner.selectOption('#wallet', assigned.wallet);
    const attendance = owner.locator('.team-record').filter({ has: owner.getByRole('heading', { name: /Attendance.*Pending/ }) });
    await actWithReason(owner, attendance, 'Approve', 'Attendance checked', 'review');
    fs.mkdirSync('.local/screenshots', { recursive: true });
    await owner.screenshot({ path: '.local/screenshots/team-owner.png', fullPage: true });
    await supervisor.reload();
    await supervisor.setViewportSize({ width: 390, height: 844 });
    assert.ok(await supervisor.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Supervisor mobile page overflows');
    await supervisor.screenshot({ path: '.local/screenshots/team-supervisor-mobile.png', fullPage: true });
    await supervisor.getByRole('button', { name: 'Sign out', exact: true }).click();
    await supervisor.waitForURL(url => url.pathname === '/login');
    assert.deepEqual(errors, []);
    console.log('PASS: separate owner/supervisor logins, account creation, assignment, funding, negative balance, REST write denial, approval, one-time correction, attendance/OT, mobile layout and logout.');
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error.stack); process.exitCode = 1; });
