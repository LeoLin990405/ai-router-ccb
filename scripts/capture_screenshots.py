#!/usr/bin/env python3
"""
Capture CCB Gateway Web UI screenshots for v0.15 documentation
Uses Playwright to automate browser screenshots
"""

from playwright.sync_api import sync_playwright
import time

def capture_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Non-headless to see what's happening
        page = browser.new_page()

        # Set viewport to a good size for screenshots
        page.set_viewport_size({"width": 1400, "height": 900})

        # Navigate to Gateway UI
        print("📱 Opening Gateway UI...")
        page.goto('http://localhost:8765')
        page.wait_for_load_state('networkidle')
        time.sleep(2)  # Extra wait for any animations

        # Screenshot 1: Costs tab
        print("💰 Capturing Costs tab...")
        page.keyboard.press('5')  # Shortcut to Costs tab
        time.sleep(1)
        page.screenshot(
            path='/Users/leo/.local/share/codex-dual/screenshots/costs.png',
            full_page=False
        )
        print("✅ Saved costs.png")

        # Screenshot 2: Requests tab with Export menu
        print("📥 Capturing Export menu...")
        page.keyboard.press('4')  # Shortcut to Requests tab
        time.sleep(1)

        # Click Export button to show dropdown
        export_button = page.locator('button:has-text("Export")').first
        if export_button.is_visible():
            export_button.click()
            time.sleep(0.5)
            page.screenshot(
                path='/Users/leo/.local/share/codex-dual/screenshots/export.png',
                full_page=False
            )
            print("✅ Saved export.png")
        else:
            print("⚠️  Export button not found")

        # Screenshot 3: Discussion Templates modal
        print("✨ Capturing Discussion Templates...")
        page.keyboard.press('3')  # Shortcut to Discussions tab
        time.sleep(1)

        # Click "Use Template" button
        template_button = page.locator('button:has-text("Use Template")').first
        if template_button.is_visible():
            template_button.click()
            time.sleep(1)  # Wait for modal to open
            page.screenshot(
                path='/Users/leo/.local/share/codex-dual/screenshots/templates.png',
                full_page=False
            )
            print("✅ Saved templates.png")
        else:
            print("⚠️  Use Template button not found")

        # Screenshot 4: Combined features (Dashboard with Qoder)
        print("🤖 Capturing Dashboard with Qoder...")
        # Close modal if open
        page.keyboard.press('Escape')
        time.sleep(0.5)
        page.keyboard.press('1')  # Shortcut to Dashboard
        time.sleep(1)
        page.screenshot(
            path='/Users/leo/.local/share/codex-dual/screenshots/dashboard-v015.png',
            full_page=False
        )
        print("✅ Saved dashboard-v015.png")

        print("\n🎉 All screenshots captured!")
        browser.close()

if __name__ == '__main__':
    print("📸 CCB Gateway Screenshot Capture Tool")
    print("=" * 50)
    print()

    # Check if Gateway is running
    import requests
    try:
        requests.get('http://localhost:8765/api/status', timeout=2)
        print("✅ Gateway is running")
        print()
    except:
        print("❌ Gateway is not running!")
        print("Please start Gateway first:")
        print("  cd ~/.local/share/codex-dual")
        print("  python3 -m lib.gateway.gateway_server --port 8765")
        exit(1)

    capture_screenshots()
