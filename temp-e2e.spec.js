const { test, expect } = require('playwright/test');

test('open login page', async ({ page }) => {
  await page.goto('https://aiworkforme-production.up.railway.app/login', { waitUntil: 'networkidle' });
  await expect(page).toHaveTitle(/Aiworkfor\.me/i);
  await page.screenshot({ path: 'temp-login.png', fullPage: true });
});
