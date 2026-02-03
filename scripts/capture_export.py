#!/usr/bin/env python3
"""
Capture Export menu screenshot manually
"""

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.set_viewport_size({"width": 1400, "height": 900})

    # Navigate
    page.goto('http://localhost:8765')
    page.wait_for_load_state('networkidle')
    time.sleep(2)

    # Go to Requests tab
    page.keyboard.press('4')
    time.sleep(2)

    # Try different selectors for Export button
    try:
        # Method 1: Text content
        export_btn = page.get_by_text('Export', exact=False)
        export_btn.click()
        time.sleep(1)
        page.screenshot(path='/Users/leo/.local/share/codex-dual/screenshots/export.png')
        print("✅ Captured export.png")
    except Exception as e:
        print(f"Method 1 failed: {e}")
        try:
            # Method 2: CSS selector
            page.locator('button:has-text("Export")').first.click()
            time.sleep(1)
            page.screenshot(path='/Users/leo/.local/share/codex-dual/screenshots/export.png')
            print("✅ Captured export.png")
        except Exception as e2:
            print(f"Method 2 failed: {e2}")
            # Just capture the page
            page.screenshot(path='/Users/leo/.local/share/codex-dual/screenshots/export.png')
            print("⚠️  Captured page without dropdown")

    time.sleep(3)
    browser.close()
