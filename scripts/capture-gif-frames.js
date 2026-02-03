const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });

    const baseUrl = 'http://127.0.0.1:8765';
    const framesDir = '/Users/leo/.local/share/codex-dual/screenshots/frames';

    // Create frames directory
    if (!fs.existsSync(framesDir)) {
        fs.mkdirSync(framesDir, { recursive: true });
    }

    console.log('Navigating to Gateway Web UI...');
    await page.goto(baseUrl);
    await page.waitForTimeout(2000);

    let frameNum = 0;
    const captureFrame = async () => {
        await page.screenshot({ path: `${framesDir}/frame_${String(frameNum).padStart(4, '0')}.png` });
        frameNum++;
    };

    // Initial Dashboard view
    console.log('Recording Dashboard...');
    for (let i = 0; i < 5; i++) {
        await captureFrame();
        await page.waitForTimeout(200);
    }

    // Click Monitor tab
    console.log('Recording Monitor tab...');
    await page.locator('button:has-text("Monitor")').first().click();
    await page.waitForTimeout(500);
    for (let i = 0; i < 10; i++) {
        await captureFrame();
        await page.waitForTimeout(200);
    }

    // Click Test tab and send request
    console.log('Recording Test tab with request...');
    await page.locator('button:has-text("Test")').first().click();
    await page.waitForTimeout(500);
    for (let i = 0; i < 5; i++) {
        await captureFrame();
        await page.waitForTimeout(200);
    }

    // Type a test message
    const textarea = await page.locator('textarea').first();
    await textarea.fill('Hello from GIF demo!');
    for (let i = 0; i < 5; i++) {
        await captureFrame();
        await page.waitForTimeout(200);
    }

    // Click Compare tab
    console.log('Recording Compare tab...');
    await page.locator('button:has-text("Compare")').first().click();
    await page.waitForTimeout(500);
    for (let i = 0; i < 10; i++) {
        await captureFrame();
        await page.waitForTimeout(200);
    }

    // Back to Dashboard
    console.log('Recording back to Dashboard...');
    await page.locator('button:has-text("Dashboard")').first().click();
    await page.waitForTimeout(500);
    for (let i = 0; i < 10; i++) {
        await captureFrame();
        await page.waitForTimeout(200);
    }

    await browser.close();
    console.log(`Done! Captured ${frameNum} frames.`);
    console.log('Run: ffmpeg -framerate 5 -i frames/frame_%04d.png -vf "scale=1200:-1" -loop 0 webui-demo.gif');
})();
