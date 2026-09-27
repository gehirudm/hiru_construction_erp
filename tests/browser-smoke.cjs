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
    assert.deepEqual(errors, [], 'Unexpected browser errors');
    console.log('PASS: login, workspaces, seeded project, and cost categories render without JavaScript errors.');
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
