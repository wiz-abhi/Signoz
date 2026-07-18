"""Final polish: trim shot 4's nav sliver; recapture shot 5 with the full panel legends."""
import os
from datetime import datetime, timezone

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "screenshots")
DASH = "019f5791-bfcb-77da-9b15-7d5fc2e1a030"
BASE = "http://localhost:8080"
START = int(datetime(2026, 7, 12, 17, 25, tzinfo=timezone.utc).timestamp() * 1000)
END = int(datetime(2026, 7, 12, 18, 20, tzinfo=timezone.utc).timestamp() * 1000)

# 1. trim 42px (14 logical @3x) off shot 4's left edge to drop the nav-text sliver
p4 = os.path.join(OUT, "4-logs-explorer-trace-filter.png")
im = Image.open(p4)
im.crop((42, 0, im.width, im.height)).save(p4)
print("trimmed shot 4 ->", Image.open(p4).size)

# 2. dashboard with room for the bottom legends
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1180, "height": 1560}, device_scale_factor=2)
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', os.environ["SIGNOZ_EMAIL"])
    pg.click('button:has-text("Next")')
    pg.wait_for_selector('input[type="password"]')
    pg.fill('input[type="password"]', os.environ["SIGNOZ_PASSWORD"])
    pg.click('button:has-text("Sign in with Password")')
    pg.wait_for_url("**/home**", timeout=30000)
    pg.goto(f"{BASE}/dashboard/{DASH}?startTime={START}&endTime={END}", wait_until="networkidle")
    pg.wait_for_timeout(11000)
    for lbl in ("Okay", "Got it"):
        try:
            pg.click(f'button:has-text("{lbl}")', timeout=1200)
        except Exception:
            pass
    pg.mouse.move(1179, 1550)
    pg.wait_for_timeout(1200)
    pg.screenshot(path=os.path.join(OUT, "5-agent-health-dashboard.png"),
                  clip={"x": 54, "y": 100, "width": 1126, "height": 1165})
    print("saved 5")
    b.close()
