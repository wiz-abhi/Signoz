import os
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
DASH = "019f5791-bfcb-77da-9b15-7d5fc2e1a030"
OUT = os.path.join(os.path.dirname(__file__), "screenshots")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 1240})
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', os.environ.get("SIGNOZ_EMAIL", "admin@example.com"))
    pg.click('button:has-text("Next")')
    pg.wait_for_selector('input[type="password"]')
    pg.fill('input[type="password"]', os.environ.get("SIGNOZ_PASSWORD", ""))
    pg.click('button:has-text("Sign in with Password")')
    pg.wait_for_url("**/home**", timeout=30000)
    pg.goto(f"{BASE}/dashboard/{DASH}?relativeTime=1h", wait_until="networkidle")
    pg.wait_for_timeout(8000)
    pg.screenshot(path=os.path.join(OUT, "5-agent-health-dashboard.png"))
    print("saved shot 5")
    b.close()
