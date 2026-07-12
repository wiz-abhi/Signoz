"""Retake screenshot 4: logs explorer filtered to the slow trace."""
import os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
EMAIL = os.environ.get("SIGNOZ_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("SIGNOZ_PASSWORD", "")
TRACE_ID = "359c33c37996f84f6cf2fc02ffd5ab03"
OUT = os.path.join(os.path.dirname(__file__), "screenshots")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 900})

    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill('input[type="email"]', EMAIL)
    page.click('button:has-text("Next")')
    page.wait_for_selector('input[type="password"]', timeout=15000)
    page.fill('input[type="password"]', PASSWORD)
    page.click('button:has-text("Sign in with Password")')
    page.wait_for_url("**/home**", timeout=30000)

    page.goto(f"{BASE}/logs/logs-explorer?relativeTime=1h", wait_until="networkidle")
    page.wait_for_timeout(2000)
    # dismiss quick-filters popup if present
    try:
        page.click('button:has-text("Okay")', timeout=3000)
    except Exception:
        pass
    page.wait_for_timeout(1000)
    # focus the query editor and type the trace filter
    qb = page.locator('[contenteditable="true"]').first
    qb.click()
    page.keyboard.press("Control+A")
    page.keyboard.press("Delete")
    page.keyboard.type(f"trace_id = '{TRACE_ID}'", delay=20)
    page.wait_for_timeout(500)
    page.keyboard.press("Escape")  # close autocomplete dropdown
    page.wait_for_timeout(300)
    page.click('button:has-text("Run Query")')
    page.wait_for_timeout(4000)
    page.screenshot(path=os.path.join(OUT, "4-logs-explorer-trace-filter.png"))
    print("saved shot 4")
    browser.close()
