"""
Recapture all blog screenshots at high DPI with tight framing.

Why: Dev.to serves body images through a CDN that downscales to width=800 and
re-encodes as lossy WebP. A 1600px-wide 1x screenshot therefore lands at 0.5x,
turning 13px UI text into ~6px mush. Since the proxy scales by WIDTH, the only
way to make text legible is to capture a NARROWER logical viewport (so content
is proportionally larger at 800px) at a HIGH device_scale_factor (so the
downscale is a clean supersample rather than a naive halving).

Time-dependent views are pinned to the original Jul 12 window via absolute
startTime/endTime epoch-ms params, so every number matches the blog text.
"""
import os
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8080"
OUT = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(OUT, exist_ok=True)

TRACE = "359c33c37996f84f6cf2fc02ffd5ab03"
SPAN_TOOL = "6c43dadb3d64715f"          # the slow `tool search_tool` span
DASH = "019f5791-bfcb-77da-9b15-7d5fc2e1a030"

DSF = 3          # supersample factor
NAV_W = 54       # left icon rail, cropped out of every shot


def ms(y, mo, d, h, mi):
    return int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp() * 1000)


# original capture window (UTC) — reproduces P99 21,818 ms exactly
SVC_START, SVC_END = ms(2026, 7, 12, 17, 55), ms(2026, 7, 12, 18, 15)
# wider window so the dashboard shows the full before/after cliff
DASH_START, DASH_END = ms(2026, 7, 12, 17, 25), ms(2026, 7, 12, 18, 20)


def login(pg):
    pg.goto(f"{BASE}/login", wait_until="networkidle")
    pg.fill('input[type="email"]', os.environ["SIGNOZ_EMAIL"])
    pg.click('button:has-text("Next")')
    pg.wait_for_selector('input[type="password"]')
    pg.fill('input[type="password"]', os.environ["SIGNOZ_PASSWORD"])
    pg.click('button:has-text("Sign in with Password")')
    pg.wait_for_url("**/home**", timeout=30000)


def dismiss_popups(pg):
    for label in ("Okay", "Got it", "Skip"):
        try:
            pg.click(f'button:has-text("{label}")', timeout=1500)
            pg.wait_for_timeout(400)
        except Exception:
            pass


def shot(pg, name, width, height, clip_h, top=0):
    """Screenshot the content area (nav rail cropped) down to clip_h logical px."""
    path = os.path.join(OUT, name)
    pg.screenshot(path=path, clip={
        "x": NAV_W, "y": top,
        "width": width - NAV_W,
        "height": min(clip_h, height - top),
    })
    print(f"saved {name}  ({(width-NAV_W)*DSF}px wide source)")


def run(pw, width, height, fn):
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": width, "height": height}, device_scale_factor=DSF)
    login(pg)
    fn(pg, width, height)
    b.close()


with sync_playwright() as pw:

    # ---- 1. Services: narrow so the table text stays readable at 800px ----
    def services(pg, w, h):
        pg.goto(f"{BASE}/services?startTime={SVC_START}&endTime={SVC_END}", wait_until="networkidle")
        pg.wait_for_selector("text=warmup-agent", timeout=30000)
        dismiss_popups(pg)
        pg.wait_for_timeout(2500)
        shot(pg, "1-services.png", w, h, clip_h=232)
    run(pw, 980, 700, services)

    # ---- 2 & 3. Trace detail: flamegraph, then the span's correlated logs ----
    def trace(pg, w, h):
        pg.goto(f"{BASE}/trace/{TRACE}?spanId={SPAN_TOOL}", wait_until="networkidle")
        pg.wait_for_selector("text=Flame Graph", timeout=30000)
        dismiss_popups(pg)
        pg.wait_for_timeout(4000)
        shot(pg, "2-trace-flamegraph.png", w, h, clip_h=h)

        pg.click('div[role="tab"]:has-text("Logs"), button:has-text("Logs")')
        pg.wait_for_timeout(3500)
        shot(pg, "3-span-related-logs.png", w, h, clip_h=h)
    run(pw, 1180, 760, trace)

    # ---- 4. Logs Explorer filtered to the hero trace ----
    def logs(pg, w, h):
        pg.goto(f"{BASE}/logs/logs-explorer?startTime={DASH_START}&endTime={DASH_END}",
                wait_until="networkidle")
        pg.wait_for_timeout(2500)
        dismiss_popups(pg)
        qb = pg.locator('[contenteditable="true"]').first
        qb.click()
        pg.keyboard.press("Control+A")
        pg.keyboard.press("Delete")
        pg.keyboard.type(f"trace_id = '{TRACE}'", delay=18)
        pg.wait_for_timeout(500)
        pg.keyboard.press("Escape")
        pg.click('button:has-text("Run Query")')
        pg.wait_for_timeout(5000)
        dismiss_popups(pg)
        shot(pg, "4-logs-explorer-trace-filter.png", w, h, clip_h=430)
    run(pw, 1080, 700, logs)

    # ---- 5. Agent Health dashboard ----
    def dash(pg, w, h):
        pg.goto(f"{BASE}/dashboard/{DASH}?startTime={DASH_START}&endTime={DASH_END}",
                wait_until="networkidle")
        pg.wait_for_timeout(9000)
        dismiss_popups(pg)
        shot(pg, "5-agent-health-dashboard.png", w, h, clip_h=h, top=48)
    run(pw, 1180, 1080, dash)

print("done")
