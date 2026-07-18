"""Print bounding boxes of candidate crop containers at the new capture viewport."""
import os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
START_MS, END_MS = 1783878900000, 1783880100000
TRACE = "359c33c37996f84f6cf2fc02ffd5ab03"
SPAN = "6c43dadb3d64715f"

VIEWS = {
    "services": f"{BASE}/services?startTime={START_MS}&endTime={END_MS}",
    "trace": f"{BASE}/trace/{TRACE}?spanId={SPAN}",
}

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 820})
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', os.environ["SIGNOZ_EMAIL"])
    pg.click('button:has-text("Next")')
    pg.wait_for_selector('input[type="password"]')
    pg.fill('input[type="password"]', os.environ["SIGNOZ_PASSWORD"])
    pg.click('button:has-text("Sign in with Password")')
    pg.wait_for_url("**/home**", timeout=30000)

    for name, url in VIEWS.items():
        pg.goto(url, wait_until="networkidle")
        pg.wait_for_timeout(6000)
        print(f"\n===== {name} =====")
        for sel in ["table", "main", ".ant-table", "[class*='Flame']", "[class*='flame']",
                    "[class*='waterfall']", "[class*='Waterfall']", "[class*='span-detail']",
                    "[class*='SpanDetail']", "[class*='content']"]:
            loc = pg.locator(sel)
            n = loc.count()
            if n:
                try:
                    bb = loc.first.bounding_box()
                    print(f"  {sel:28s} n={n:2d} bb={bb}")
                except Exception:
                    pass
    b.close()
