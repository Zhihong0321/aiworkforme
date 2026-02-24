import { chromium } from 'playwright';

(async () => {
    const browser = await chromium.launch();
    const context = await browser.newContext();
    const page = await context.newPage();

    page.on('console', msg => {
        if (msg.type() === 'error' || msg.type() === 'warning') {
            console.log(`[${msg.type()}] ${msg.text()}`);
        }
    });
    
    page.on('pageerror', error => {
        console.log(`[pageerror] ${error.message}`);
    });

    console.log("Navigating to production site...");
    await page.goto("https://aiworkforme-production.up.railway.app/");
    
    // Login
    await page.fill('input[type="email"]', '2@2.com');
    await page.fill('input[type="password"]', '1234');
    await page.click('button:has-text("Sign In")');
    
    await page.waitForTimeout(3000);
    
    console.log("Navigating to Dashboard...");
    await page.goto("https://aiworkforme-production.up.railway.app/home");
    await page.waitForTimeout(2000);

    console.log("Navigating to Calendar...");
    await page.goto("https://aiworkforme-production.up.railway.app/calendar");
    await page.waitForTimeout(2000);

    console.log("Navigating to Playground...");
    await page.goto("https://aiworkforme-production.up.railway.app/playground");
    await page.waitForTimeout(2000);

    console.log("Navigating to Contacts...");
    await page.goto("https://aiworkforme-production.up.railway.app/leads");
    await page.waitForTimeout(2000);

    await browser.close();
})();
