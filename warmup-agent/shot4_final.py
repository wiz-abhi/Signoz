"""Shot 4, final: clip below the top nav strip and end exactly on a log-row boundary."""
import os
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
OUT = os.path.join(os.path.dirname(__file__), "screenshots")
TRACE = "359c33c37996f84f6cf2fc02ffd5ab03"
START = int(datetime(2026, 7, 12, 17, 25, tzinfo=timezone.utc).timestamp() * 1000)
END = int(datetime(2026, 7, 12, 18, 20, tzinfo=timezone.utc).timestamp() * 1000)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1180, "height": 760}, device_scale_factor=3)
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', os.environ["SIGNOZ_EMAIL"])
    pg.click('button:has-text("Next")')
    pg.wait_for_selector('input[type="password"]')
    pg.fill('input[type="password"]', os.environ["SIGNOZ_PASSWORD"])
    pg.click('button:has-text("Sign in with Password")')
    pg.wait_for_url("**/home**", timeout=30000)

    pg.goto(f"{BASE}/logs/logs-explorer?startTime={START}&endTime={END}", wait_until="networkidle")
    pg.wait_for_timeout(2500)
    for lbl in ("Okay", "Got it"):
        try:
            pg.click(f'button:has-text("{lbl}")', timeout=1200)
        except Exception:
            pass
    qb = pg.locator('[contenteditable="true"]').first
    qb.click()
    pg.keyboard.press("Control+A")
    pg.keyboard.press("Delete")
    pg.keyboard.type(f"trace_id = '{TRACE}'", delay=18)
    pg.wait_for_timeout(400)
    pg.keyboard.press("Escape")
    pg.click('button:has-text("Run Query")')
    pg.wait_for_timeout(5500)

    xs = []
    for sel in ['[contenteditable="true"]', 'button:has-text("List View")']:
        try:
            bb = pg.locator(sel).first.bounding_box()
            if bb:
                xs.append(bb["x"])
        except Exception:
            pass
    left = max(60, min(xs) - 14) if xs else 234

    # bottom = bottom edge of the last log row that is fully in view
    rows = pg.locator('div:has-text("INFO:warmup-agent"), div:has-text("WARNING:warmup-agent")')
    bottom = None
    try:
        boxes = []
        for i in range(rows.count()):
            bb = rows.nth(i).bounding_box()
            if bb and bb["height"] < 40 and bb["y"] > 100:
                boxes.append(bb["y"] + bb["height"])
        boxes = [v for v in sorted(set(boxes)) if v < 745]
        if boxes:
            bottom = boxes[-1] + 3
    except Exception:
        pass
    top = 30
    height = (bottom - top) if bottom else 400
    print(f"left={left} top={top} bottom={bottom} height={height}")

    pg.mouse.move(1179, 750)
    pg.wait_for_timeout(1200)
    pg.screenshot(path=os.path.join(OUT, "4-logs-explorer-trace-filter.png"),
                  clip={"x": left, "y": top, "width": 1180 - left, "height": height})
    print("saved 4")
    b.close()
