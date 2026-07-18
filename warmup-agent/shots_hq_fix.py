"""Fix pass: shot 4 (crop past the filters sidebar, kill hover tooltip) and shot 5 (fit all 4 panels)."""
import os
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
OUT = os.path.join(os.path.dirname(__file__), "screenshots")
TRACE = "359c33c37996f84f6cf2fc02ffd5ab03"
DASH = "019f5791-bfcb-77da-9b15-7d5fc2e1a030"
DSF = 3


def ms(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp() * 1000)


START, END = ms(2026, 7, 12, 17, 25), ms(2026, 7, 12, 18, 20)


def login(pg):
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', os.environ["SIGNOZ_EMAIL"])
    pg.click('button:has-text("Next")')
    pg.wait_for_selector('input[type="password"]')
    pg.fill('input[type="password"]', os.environ["SIGNOZ_PASSWORD"])
    pg.click('button:has-text("Sign in with Password")')
    pg.wait_for_url("**/home**", timeout=30000)


def dismiss(pg):
    for label in ("Okay", "Got it", "Skip"):
        try:
            pg.click(f'button:has-text("{label}")', timeout=1200)
            pg.wait_for_timeout(300)
        except Exception:
            pass


with sync_playwright() as pw:
    # ---- shot 4 ----
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1180, "height": 700}, device_scale_factor=DSF)
    login(pg)
    pg.goto(f"{BASE}/logs/logs-explorer?startTime={START}&endTime={END}", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    dismiss(pg)
    qb = pg.locator('[contenteditable="true"]').first
    qb.click()
    pg.keyboard.press("Control+A")
    pg.keyboard.press("Delete")
    pg.keyboard.type(f"trace_id = '{TRACE}'", delay=18)
    pg.wait_for_timeout(400)
    pg.keyboard.press("Escape")
    pg.click('button:has-text("Run Query")')
    pg.wait_for_timeout(5000)
    dismiss(pg)

    # crop past the filters sidebar: use the leftmost of the query bar / view toolbar
    xs = []
    for sel in ['[contenteditable="true"]', 'button:has-text("List View")']:
        try:
            bb = pg.locator(sel).first.bounding_box()
            if bb:
                xs.append(bb["x"])
        except Exception:
            pass
    left = max(60, min(xs) - 14) if xs else 340
    print("shot4 left crop =", left)

    # park the mouse off-canvas so no hover tooltip renders
    pg.mouse.move(1179, 690)
    pg.wait_for_timeout(1200)

    pg.screenshot(path=os.path.join(OUT, "4-logs-explorer-trace-filter.png"),
                  clip={"x": left, "y": 0, "width": 1180 - left, "height": 420})
    print("saved 4")
    b.close()

    # ---- shot 5: taller viewport so all four panels are complete ----
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1180, "height": 1500}, device_scale_factor=2)
    login(pg)
    pg.goto(f"{BASE}/dashboard/{DASH}?startTime={START}&endTime={END}", wait_until="networkidle")
    pg.wait_for_timeout(10000)
    dismiss(pg)
    pg.mouse.move(1179, 1490)
    pg.wait_for_timeout(1000)
    pg.screenshot(path=os.path.join(OUT, "5-agent-health-dashboard.png"),
                  clip={"x": 54, "y": 100, "width": 1126, "height": 1080})
    print("saved 5")
    b.close()
