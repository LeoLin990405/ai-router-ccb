const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

    const baseUrl = 'http://127.0.0.1:8765';
    const screenshotsDir = '/Users/leo/.local/share/codex-dual/screenshots';

    console.log('Navigating to Gateway Web UI...');
    await page.goto(baseUrl);
    await page.waitForTimeout(3000);

    // Take initial screenshot (Dashboard is default)
    console.log('Capturing Dashboard...');
    await page.screenshot({ path: `${screenshotsDir}/dashboard.png` });
    console.log('  ✓ Saved dashboard.png');

    // Tab names to click
    const tabs = ['Monitor', 'Requests', 'Test', 'Compare', 'API Keys', 'Config'];

    for (const tabName of tabs) {
        console.log(`Capturing ${tabName} tab...`);
        try {
            // Find and click the tab button
            const tabButton = await page.locator(`button:has-text("${tabName}")`).first();
            await tabButton.click({ timeout: 5000 });
            await page.waitForTimeout(1500);

            const filename = tabName.toLowerCase().replace(' ', '-');
            await page.screenshot({ path: `${screenshotsDir}/${filename}.png` });
            console.log(`  ✓ Saved ${filename}.png`);
        } catch (e) {
            console.log(`  ✗ Failed: ${e.message.split('\n')[0]}`);
        }
    }

    await browser.close();
    console.log('Done!');
})();
