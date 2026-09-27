const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

async function main() {
  const env = Object.fromEntries(fs.readFileSync('.env', 'utf8').split('\n').filter(l => l && !l.startsWith('#')).map(l => {
    const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1)];
  }));
  const base = `http://localhost:${process.env.HIRU_TEST_PORT || env.HIRU_TEST_PORT || 8081}`;
  const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const browser = await chromium.launch({ headless: true, executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || (fs.existsSync(chrome) ? chrome : undefined) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
  const page = await context.newPage();
  page.setDefaultTimeout(20000);
  let invoice, receipt, csrf;
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  async function call(method, args) {
    const response = await context.request.post(base + '/api/method/' + method, {
      headers: { 'X-Frappe-CSRF-Token': csrf }, data: args
    });
    const data = await response.json();
    assert.equal(response.ok(), true, JSON.stringify(data));
    return data.message;
  }
  try {
    await page.goto(base + '/construction?project=UI-DAILY-PROJECT');
    await page.waitForURL(url => url.pathname === '/login');
    await page.locator('#login_email').fill('Administrator');
    await page.locator('#login_password').fill(env.PILOT_ADMIN_PASSWORD);
    await page.locator('.btn-login:not(.btn-login-with-email-link)').click();
    await page.waitForURL(url => url.pathname === '/construction');
    await page.locator('#content').waitFor();
    csrf = await page.locator('meta[name="csrf-token"]').getAttribute('content');
    await page.selectOption('#project', 'UI-DAILY-PROJECT');
    await page.waitForFunction(() => document.querySelector('#project-title').textContent === 'Daily view test project');
    const before = await call('hiru_construction.daily.overview', { project: 'UI-DAILY-PROJECT' });
    fs.mkdirSync('.local/screenshots', { recursive: true });
    await page.screenshot({ path: '.local/screenshots/daily-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Mobile page overflows');
    await page.screenshot({ path: '.local/screenshots/daily-mobile.png', fullPage: true });
    await page.getByRole('button', { name: 'Record expense' }).click();
    await page.selectOption('#category', before.categories[0].account);
    await page.fill('#description', 'UI test delivery');
    await page.selectOption('#supplier', { label: 'Daily UI Supplier' });
    await page.fill('#amount', '123.45');
    await page.locator('#receipt').setInputFiles({ name: 'receipt.png', mimeType: 'image/png',
      buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64') });
    await page.screenshot({ path: '.local/screenshots/daily-expense-mobile.png', fullPage: true });
    const saved = page.waitForResponse(r => r.url().includes('/daily.save_expense') || r.url().endsWith('daily.save_expense'));
    const uploaded = page.waitForResponse(r => r.url().endsWith('/upload_file'));
    await page.getByRole('button', { name: 'Save draft & review' }).click();
    const saveData = await (await saved).json();
    assert.ok(saveData.message?.name, JSON.stringify(saveData)); invoice = saveData.message.name;
    const uploadData = await (await uploaded).json(); receipt = uploadData.message;
    assert.ok(receipt?.is_private, 'Receipt must be private');
    await page.getByRole('button', { name: 'Confirm & record expense' }).waitFor();
    await page.waitForFunction(() => !document.querySelector('#post-expense').disabled);
    assert.equal((await call('hiru_construction.daily.overview', { project: 'UI-DAILY-PROJECT' })).spent, before.spent, 'Draft affected costs');
    const guest = await browser.newContext();
    const denied = await guest.request.get(base + receipt.file_url);
    assert.ok([403, 404].includes(denied.status()), 'Guest downloaded a private receipt');
    await guest.close();
    await page.getByRole('button', { name: 'Confirm & record expense' }).click();
    await page.getByRole('heading', { name: 'Expense recorded', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('#content').hidden);
    const after = await call('hiru_construction.daily.overview', { project: 'UI-DAILY-PROJECT' });
    assert.equal(after.spent, before.spent + 123.45);
    await page.getByRole('button').filter({ hasText: invoice }).click();
    await page.getByRole('heading', { name: 'Expense recorded', exact: true }).waitFor();
    assert.deepEqual(errors, [], 'JavaScript errors');
    console.log('PASS: daily home, mobile layout, private receipt, draft review, posting, totals and reopening.');
  } finally {
    if (invoice && csrf) {
      const doc = await call('hiru_construction.daily.expense', { name: invoice });
      if (doc.docstatus === 1) await call('frappe.client.cancel', { doctype: 'Purchase Invoice', name: invoice });
      if (receipt?.name) await call('frappe.client.delete', { doctype: 'File', name: receipt.name });
      if (doc.docstatus === 0) await call('frappe.client.delete', { doctype: 'Purchase Invoice', name: invoice });
    }
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
