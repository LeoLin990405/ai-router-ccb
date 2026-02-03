#!/usr/bin/env python3
"""Capture Web UI screenshots showing real CCB requests"""

from playwright.sync_api import sync_playwright
import time

def capture_real_requests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 900})

        # Go to Web UI
        page.goto('http://localhost:8765/')
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        # Capture dashboard with real stats
        page.screenshot(path='assets/demo/real-dashboard.png', full_page=False)
        print("Captured: real-dashboard.png")

        # Go to Requests tab
        page.click('text=Requests')
        time.sleep(1)
        page.wait_for_load_state('networkidle')

        # Capture requests list showing real requests
        page.screenshot(path='assets/demo/real-requests.png', full_page=False)
        print("Captured: real-requests.png")

        # Click on first request to show details
        try:
            page.click('table tbody tr:first-child', timeout=5000)
            time.sleep(1)
            page.screenshot(path='assets/demo/real-request-detail.png', full_page=False)
            print("Captured: real-request-detail.png")
        except:
            print("No requests to click")

        browser.close()
        print("Done!")

if __name__ == '__main__':
    capture_real_requests()
