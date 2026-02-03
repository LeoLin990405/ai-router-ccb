#!/usr/bin/env python3
"""Capture Web UI screenshots for README."""

from playwright.sync_api import sync_playwright
import time

SCREENSHOTS_DIR = "/Users/leo/.local/share/codex-dual/screenshots"

def capture_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use larger viewport for better screenshots
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # Navigate to Web UI
        page.goto("http://localhost:8765/")
        page.wait_for_load_state("networkidle")
        time.sleep(2)  # Wait for animations

        # 1. Dashboard screenshot
        print("Capturing Dashboard...")
        page.screenshot(path=f"{SCREENSHOTS_DIR}/dashboard.png", full_page=False)

        # 2. Requests tab
        print("Capturing Requests...")
        page.click("text=Requests")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path=f"{SCREENSHOTS_DIR}/requests.png", full_page=False)

        # 3. Click on a request to show details (if any exist)
        try:
            # Try to click on first request row
            rows = page.locator("table tbody tr")
            if rows.count() > 0:
                rows.first.click()
                time.sleep(1)
                page.screenshot(path=f"{SCREENSHOTS_DIR}/request-detail.png", full_page=False)
                # Close modal
                page.keyboard.press("Escape")
                time.sleep(0.5)
        except Exception as e:
            print(f"Could not capture request detail: {e}")

        # 4. Test tab
        print("Capturing Test Console...")
        page.click("text=Test")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path=f"{SCREENSHOTS_DIR}/test-console.png", full_page=False)

        # 5. Compare tab
        print("Capturing Compare...")
        page.click("text=Compare")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path=f"{SCREENSHOTS_DIR}/compare.png", full_page=False)

        # 6. API Keys tab
        print("Capturing API Keys...")
        page.click("text=API Keys")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path=f"{SCREENSHOTS_DIR}/api-keys.png", full_page=False)

        # 7. Config tab
        print("Capturing Config...")
        page.click("text=Config")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path=f"{SCREENSHOTS_DIR}/config.png", full_page=False)

        # 8. Light theme screenshot
        print("Capturing Light Theme...")
        page.click("text=Dashboard")
        page.wait_for_load_state("networkidle")
        time.sleep(0.5)
        # Find and click theme toggle button
        try:
            theme_btn = page.locator("button:has(i.fa-sun), button:has(i.fa-moon)").first
            theme_btn.click()
            time.sleep(1)
            page.screenshot(path=f"{SCREENSHOTS_DIR}/dashboard-light.png", full_page=False)
            # Switch back to dark
            theme_btn.click()
        except Exception as e:
            print(f"Could not capture light theme: {e}")

        browser.close()
        print(f"\nScreenshots saved to {SCREENSHOTS_DIR}/")

if __name__ == "__main__":
    capture_screenshots()
