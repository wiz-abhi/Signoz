"""Probe: can we pin the services page to the original Jul 12 window via URL params?"""
import os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
EMAIL = os.environ.get("SIGNOZ_EMAIL")
PASSWORD = os.environ.get("SIGNOZ_PASSWORD")

START_MS = 1783878900000  # Jul 12 2026 17:55 UTC
END_MS = 1783880100000    # Jul 12 2026 18:15 UTC

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', EMAIL)
    pg.click('button:has-text("Next")')
    pg.wait_for_selector('input[type="password"]')
    pg.fill('input[type="password"]', PASSWORD)
    pg.click('button:has-text("Sign in with Password")')
    pg.wait_for_url("**/home**", timeout=30000)

    for label, url in [
        ("abs startTime/endTime", f"{BASE}/services?startTime={START_MS}&endTime={END_MS}"),
        ("relativeTime=7d", f"{BASE}/services?relativeTime=7d"),
    ]:
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_timeout(5000)
        try:
            pg.wait_for_selector("text=warmup-agent", timeout=15000)
            row = pg.locator("tr", has_text="warmup-agent").first.inner_text().replace("\n", " | ")
        except Exception as e:
            row = f"NO ROW ({type(e).__name__})"
        print(f"[{label}]\n   {row}\n   url now: {pg.url[:120]}")
    b.close()
