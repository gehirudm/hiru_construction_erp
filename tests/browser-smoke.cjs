const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

async function main() {
  const env = Object.fromEntries(fs.readFileSync('.env', 'utf8').trim().split('\n')
    .filter(line => line && !line.startsWith('#')).map(line => {
      const index = line.indexOf('=');
      return [line.slice(0, index), line.slice(index + 1)];
    }));
  const base = `http://localhost:${env.PILOT_PORT || 8080}`;
  const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ||
      (fs.existsSync(chrome) ? chrome : undefined),
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    page.setDefaultTimeout(15000);
    const errors = [];
    page.on('response', response => { if (response.status() >= 400) console.error('HTTP', response.status(), response.url()); });
    page.on('pageerror', error => { errors.push(error.message); console.error('Browser:', error.stack); });
    await page.goto(base + '/login');
    await page.waitForFunction(() => typeof window.login?.call === 'function');
    await page.locator('#login_email').fill('Administrator');
    await page.locator('#login_password').fill(env.PILOT_ADMIN_PASSWORD);
    await page.locator('.btn-login:not(.btn-login-with-email-link)').click();
    try {
      await page.waitForURL(url => !url.pathname.startsWith('/login'), { timeout: 15000, waitUntil: 'domcontentloaded' });
    } catch (error) {
      console.error('Login message:', await page.locator('.login-error-banner').allTextContents());
      throw error;
    }
    await page.goto(base + '/construction?project=PILOT-PROJECT-001');
    await page.waitForFunction(() => /[0-9]/.test(document.querySelector('#spent').textContent));
    const displayedAmount = async id => Number((await page.locator('#' + id).textContent()).replace(/[^0-9.-]/g, ''));
    const overview = { budget: await displayedAmount('budget'), actual: await displayedAmount('spent'),
      commitment: await displayedAmount('orders'), remaining: await displayedAmount('remaining') };
    const totalText = overview.actual.toLocaleString('en-US', { minimumFractionDigits: 2 });
    fs.mkdirSync('.local/screenshots', { recursive: true });
    await page.screenshot({ path: '.local/screenshots/daily-demo.png', fullPage: true });
    await page.getByRole('button', { name: 'All expenses', exact: true }).click();
    const expenseTotal = async amount => page.waitForFunction(value =>
      document.querySelector('#expenses-summary')?.textContent.includes(value), amount);
    await expenseTotal(totalText);
    assert.match(await page.locator('.expense-table tbody tr').last().locator('td').last().textContent(), new RegExp(totalText.replace('.', '\\.')));
    await page.locator('.expense-filters select[name=category]').selectOption({ label: 'Fuel' });
    await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
    await expenseTotal('9,000');
    assert.match(await page.locator('.expense-table tbody tr').last().locator('td').last().textContent(), /9,000/);
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    await expenseTotal(totalText);
    await page.locator('.expense-filters select[name=source]').selectOption('Purchase Invoice');
    await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
    await page.waitForFunction(() => [...document.querySelectorAll('.expense-table tbody tr')].every(row => row.cells[3].textContent.includes('Purchase Invoice')));
    assert.ok(await page.locator('.expense-table tbody tr').count());
    await page.locator('.expense-filters input[name=search]').fill('no-such-expense-reference');
    await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
    await expenseTotal('0 entries');
    await page.getByRole('button', { name: 'Clear filters', exact: true }).click();
    await expenseTotal(totalText);
    await page.screenshot({ path: '.local/screenshots/expenses-demo.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Mobile page must fit the viewport');
    await page.screenshot({ path: '.local/screenshots/expenses-mobile.png', fullPage: true });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.getByRole('button', { name: 'Attendance & OT', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('.crew-row').length === 3);
    await page.screenshot({ path: '.local/screenshots/crew-demo.png', fullPage: true });
    await page.getByRole('button', { name: 'Expense categories', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('.category-card').length === 5);
    await page.screenshot({ path: '.local/screenshots/categories-demo.png', fullPage: true });
    await page.getByRole('link', { name: 'Site team & money', exact: true }).click();
    await page.getByRole('button', { name: 'People & access', exact: true }).click();
    await page.getByRole('heading', { name: 'Create a login', exact: true }).waitFor();
    await page.screenshot({ path: '.local/screenshots/team-setup-demo.png', fullPage: true });
    await page.goto(base + '/desk/hiru-construction');
    await page.getByText('Construction Cost Category', { exact: true }).first().waitFor();
    fs.mkdirSync('.local/screenshots', { recursive: true });
    await page.screenshot({ path: '.local/screenshots/workspace.png', fullPage: true });
    await page.goto(base + '/desk/project/PILOT-PROJECT-001');
    const projectName = page.locator('input[data-fieldname="project_name"]');
    await projectName.waitFor();
    assert.equal(await projectName.inputValue(), 'DEMO — Community Hall Renovation');
    await page.screenshot({ path: '.local/screenshots/project.png', fullPage: true });
    await page.goto(base + '/desk/hiru-construction');
    await page.getByText('Hiru Construction', { exact: true }).first().waitFor();
    await page.getByText('Construction Cost Category', { exact: true }).first().waitFor();
    await page.goto(base + '/desk/construction-cost-category');
    await page.getByText('Materials', { exact: true }).first().waitFor();
    await page.screenshot({ path: '.local/screenshots/categories.png', fullPage: true });
    await page.goto(base + '/desk/query-report/Construction%20Project%20Costs?project=PILOT-PROJECT-001');
    await page.waitForFunction(() => window.frappe?.query_report?.data?.length === 5);
    const totals = await page.evaluate(() => frappe.query_report.data.reduce((sum, row) => ({
      budget: sum.budget + row.current_budget, actual: sum.actual + row.actual,
      commitment: sum.commitment + row.commitment, remaining: sum.remaining + row.remaining_budget
    }), { budget: 0, actual: 0, commitment: 0, remaining: 0 }));
    assert.deepEqual(totals, overview, 'Detailed report must reconcile with the daily overview');
    await page.waitForFunction(() => [...document.querySelectorAll('.chart-container .bar')]
      .some(bar => bar.getBoundingClientRect().height > 5));
    await page.screenshot({ path: '.local/screenshots/project-costs.png', fullPage: true });
    await page.goto(base + '/desk/construction-cost-plan/PILOT-TENDER-001');
    await page.getByRole('button', { name: 'Create Revision', exact: true }).click();
    await page.waitForFunction(() => window.cur_frm?.doc?.version_kind === 'Approved revision');
    const revision = await page.evaluate(() => ({
      baseline: cur_frm.doc.baseline, rows: cur_frm.doc.items.length,
      preservesTender: cur_frm.doc.items.every(row => row.original_estimate === row.approved_revision)
    }));
    assert.deepEqual(revision, { baseline: 'PILOT-TENDER-001', rows: 4, preservesTender: true });
    assert.deepEqual(errors, [], 'Unexpected browser errors');
    console.log('PASS: expense totals, filters and mobile layout; login, workspace, project, categories, cost report and revision form without JavaScript errors.');
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error.stack); process.exitCode = 1; });
