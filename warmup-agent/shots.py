"""Capture blog screenshots from local SigNoz UI."""
import os
import sys
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
EMAIL = os.environ.get("SIGNOZ_EMAIL", "admin@example.com")
PASSWORD = os.environ.get("SIGNOZ_PASSWORD", "")
TRACE_URL = f"{BASE}/trace/359c33c37996f84f6cf2fc02ffd5ab03?spanId=6c43dadb3d64715f"
OUT = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(OUT, exist_ok=True)


def shot(page, name):
    path = os.path.join(OUT, name)
    page.screenshot(path=path)
    print("saved", path)


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1600, "height": 900})

    # login
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.fill('input[type="email"]', EMAIL)
    page.click('button:has-text("Next")')
    page.wait_for_selector('input[type="password"]', timeout=15000)
    page.fill('input[type="password"]', PASSWORD)
    page.click('button:has-text("Sign in with Password")')
    page.wait_for_url("**/home**", timeout=30000)
    print("logged in")

    # 1. services list with warmup-agent P99
    page.goto(f"{BASE}/services?relativeTime=1h", wait_until="networkidle")
    page.wait_for_selector("text=warmup-agent", timeout=30000)
    page.wait_for_timeout(2000)
    shot(page, "1-services.png")

    # 2. trace detail flamegraph (agent answer selected by default spanId param -> search_tool)
    page.goto(TRACE_URL, wait_until="networkidle")
    page.wait_for_selector("text=Flame Graph", timeout=30000)
    page.wait_for_timeout(3000)
    shot(page, "2-trace-flamegraph.png")

    # 3. money shot: search_tool span -> Logs tab (related logs)
    page.click('div[role="tab"]:has-text("Logs"), button:has-text("Logs")')
    page.wait_for_timeout(3000)
    shot(page, "3-span-related-logs.png")

    # 4. logs explorer filtered by trace_id showing retry warnings
    page.goto(
        f"{BASE}/logs/logs-explorer?relativeTime=1h",
        wait_until="networkidle",
    )
    page.wait_for_timeout(2000)
    # type filter expression into the query search bar
    try:
        qb = page.locator('[contenteditable="true"], textarea.monaco, .view-line').first
        qb.click()
        page.keyboard.type("trace_id = '07989155019928eec9707c02ac594662'")
        page.keyboard.press("Enter")
        page.wait_for_timeout(4000)
    except Exception as e:
        print("filter typing failed:", e)
    shot(page, "4-logs-explorer-trace-filter.png")

    browser.close()
print("all done")
