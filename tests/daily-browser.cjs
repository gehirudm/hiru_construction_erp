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
  let invoice, receipt, csrf, fuelInvoice, attendanceName, mealInvoice;
  const errors = [];
  page.on('pageerror', error => { errors.push(error.message); console.error('Browser error:', error.message); });
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
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.selectOption('#project', 'UI-SITE-PROJECT');
    await page.waitForFunction(() => document.querySelector('#project-title').textContent === 'Site workflow test');
    await page.getByRole('button', { name: 'Attendance & OT', exact: true }).click();
    await page.locator('.crew-row').waitFor();
    await page.getByRole('button', { name: 'Mark all present', exact: true }).click();
    await page.locator('[data-ot]').fill('2');
    await page.screenshot({ path: '.local/screenshots/crew-mobile.png', fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.getByRole('button', { name: 'Save attendance draft', exact: true }).click();
    await page.getByText('1 workers saved as drafts.', { exact: true }).waitFor();
    const crew = await call('hiru_construction.site_work.crew', { project: 'UI-SITE-PROJECT' });
    attendanceName = crew.employees[0].attendance.name;
    assert.equal(crew.employees[0].attendance.docstatus, 0);
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByRole('button', { name: 'Review & confirm attendance', exact: true }).click();
    await page.getByRole('button', { name: 'Confirm this attendance', exact: true }).click();
    await page.getByText('1 workers confirmed.', { exact: true }).waitFor();
    assert.equal((await call('hiru_construction.site_work.crew', { project: 'UI-SITE-PROJECT' })).ot_total, 2);
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByRole('button', { name: 'Expense categories', exact: true }).click();
    await page.locator('.category-card').click();
    await page.getByRole('button', { name: 'Add fuel expense', exact: true }).click();
    await page.selectOption('#fuel-equipment', 'UI-SITE-TRUCK');
    await page.fill('#fuel-litres', '10');
    await page.fill('#fuel-meter', '120');
    await page.selectOption('#supplier', { label: 'Daily UI Supplier' });
    await page.fill('#amount', '3000.25');
    await page.screenshot({ path: '.local/screenshots/fuel-mobile.png', fullPage: true });
    const fuelSaved = page.waitForResponse(r => r.url().endsWith('daily.save_expense'));
    await page.getByRole('button', { name: 'Save draft & review' }).click();
    const fuelData = await (await fuelSaved).json();
    assert.ok(fuelData.message?.name, JSON.stringify(fuelData)); fuelInvoice = fuelData.message.name;
    assert.equal(fuelData.message.vehicle, 'UI-SITE-TRUCK');
    assert.equal(fuelData.message.litres, 10);
    await page.getByRole('button', { name: 'Confirm & record expense' }).click();
    await page.getByRole('heading', { name: 'Expense recorded', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.getByRole('button', { name: 'Fuel & equipment', exact: true }).click();
    await page.locator('#work-panel').getByText('UI-SITE-TRUCK', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Expense categories', exact: true }).click();
    await page.locator('.category-card').click();
    await page.getByText(/Spent LKR\s*3,000.25/).waitFor();
    await page.screenshot({ path: '.local/screenshots/category-detail-mobile.png', fullPage: true });
    await page.locator('#close-work-dialog').click();
    await page.selectOption('#project', 'UI-MEALS-PROJECT');
    await page.waitForFunction(() => document.querySelector('#project-title').textContent === 'Meals workflow test');
    await page.getByRole('button', { name: 'Meals', exact: true }).click();
    await page.getByText('2 people suggested from confirmed present/half-day attendance. Adjust separately for each meal.', { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Expected costs per person', exact: true }).click();
    await page.locator('[data-meal-type="Lunch"]').fill('100');
    await page.getByRole('button', { name: 'Save expected costs', exact: true }).click();
    await page.locator('#work-dialog').waitFor({ state: 'hidden' });
    const lunch = page.locator('#work-panel .category-card').filter({ has: page.getByRole('heading', { name: 'Lunch', exact: true }) });
    const edit = lunch.getByRole('button', { name: 'Adjust diners', exact: true });
    if (await edit.count()) await edit.click();
    else await lunch.getByRole('button', { name: 'Set up lunch', exact: true }).click();
    await page.fill('#meal-diners', '1'); await page.fill('#meal-reason', 'One worker did not take lunch');
    await page.getByRole('button', { name: 'Save meal headcount', exact: true }).click();
    await page.locator('#work-dialog').waitFor({ state: 'hidden' });
    await lunch.getByRole('button', { name: 'Add lunch expense', exact: true }).click();
    await page.selectOption('#supplier', { label: 'Daily UI Supplier' }); await page.fill('#amount', '150');
    const invalidMealFields = await page.locator('#expense-form').evaluate(form => [...form.querySelectorAll('input,select')]
      .filter(input => !input.checkValidity()).map(input => ({ id: input.id, value: input.value, message: input.validationMessage })));
    assert.deepEqual(invalidMealFields, [], 'Meal expense form is invalid');
    const mealSaved = page.waitForResponse(r => r.url().endsWith('daily.save_expense'));
    await page.getByRole('button', { name: 'Save draft & review' }).click();
    const mealResponse = await mealSaved.catch(async error => {
      console.error('Meal entry status:', await page.locator('#expense-error').textContent(),
        await page.locator('#save-draft').textContent());
      throw error;
    });
    const mealData = await mealResponse.json();
    assert.ok(mealData.message?.name, JSON.stringify(mealData)); mealInvoice = mealData.message.name;
    await page.getByText(/OVER EXPECTED COST/).waitFor();
    await page.getByRole('button', { name: 'Confirm & record expense' }).click();
    await page.getByRole('heading', { name: 'Expense recorded', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Done', exact: true }).click();
    await page.locator('#meal-alert').waitFor();
    await lunch.getByText(/LKR\s*50.00 over this meal/).waitFor();
    await page.screenshot({ path: '.local/screenshots/meals-mobile.png', fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, [], 'JavaScript errors');
    console.log('PASS: daily home, receipts, attendance/OT, fuel, categories, meal attendance suggestion, adjusted diners and over-limit alerts.');
  } finally {
    if (mealInvoice && csrf) {
      const doc = await call('hiru_construction.daily.expense', { name: mealInvoice });
      if (doc.docstatus === 1) await call('frappe.client.cancel', { doctype: 'Purchase Invoice', name: mealInvoice });
      else if (doc.docstatus === 0) await call('frappe.client.delete', { doctype: 'Purchase Invoice', name: mealInvoice });
    }
    if (attendanceName && csrf) {
      const doc = await call('frappe.client.get', { doctype: 'Attendance', name: attendanceName });
      if (doc.docstatus === 1) await call('frappe.client.cancel', { doctype: 'Attendance', name: attendanceName });
      else if (doc.docstatus === 0) await call('frappe.client.delete', { doctype: 'Attendance', name: attendanceName });
    }
    if (fuelInvoice && csrf) {
      const doc = await call('hiru_construction.daily.expense', { name: fuelInvoice });
      if (doc.docstatus === 1) await call('frappe.client.cancel', { doctype: 'Purchase Invoice', name: fuelInvoice });
      else if (doc.docstatus === 0) await call('frappe.client.delete', { doctype: 'Purchase Invoice', name: fuelInvoice });
    }
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
